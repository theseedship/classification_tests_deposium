// Resident transport for the pinned upstream's untrained embedding decisions.
// This bridge does not train, download, classify by local rules, or chunk text.
package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"slices"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unicode/utf8"

	"github.com/bornholm/indecis"
	"github.com/bornholm/indecis/tokenizer"
)

const (
	maxLine          = 1024 * 1024
	sourceRevision   = "339e191405ac9be90f6857f810f478b3312b7f35"
	backboneRevision = "c721113d59a1d91b447450324f51c4b3332c924a"
)

var prompt = map[string]any{
	"schema_version": "deposium.indecis-choice-prompt/v1", "input_protocol": "context_choice",
	"mode": "open_untrained", "state_field": "context", "instruction_field": "question",
	"options_field": "options", "output_field": "choice_id",
	"option_serialization": "description_newline_question", "cache_policy": "request_local", "trained": false,
}

type configuration struct {
	LocalDir       string
	Revision       string
	SourceRevision string
	MaxLength      int
	Threads        int
}

type option struct{ ID, Description string }
type choiceInput struct {
	Context, Question string
	Options           []option
}
type fullTokenizer interface{ Encode(string) []int32 }
type decisionEngine interface {
	TokenIDs(indecis.Input) ([]int32, error)
	DecideOpen(context.Context, []indecis.OpenQuestion, ...string) ([]indecis.Decision, error)
}

type worker struct {
	engine    decisionEngine
	tokenizer fullTokenizer
	maxLength int
}
type envelope struct {
	Status string `json:"status"`
	Output any    `json:"output"`
	Error  any    `json:"error"`
	Raw    any    `json:"raw_output"`
}

// Decoder.Token exposes object keys so duplicates cannot be overwritten by Go.
func jsonValue(d *json.Decoder, depth int) (any, error) {
	if depth > 32 {
		return nil, errors.New("protocol_limit")
	}
	t, err := d.Token()
	if err != nil {
		return nil, err
	}
	delimiter, compound := t.(json.Delim)
	if !compound {
		return t, nil
	}
	switch delimiter {
	case '{':
		out := map[string]any{}
		for d.More() {
			key, err := d.Token()
			if err != nil {
				return nil, err
			}
			name, ok := key.(string)
			if !ok {
				return nil, errors.New("protocol_invalid")
			}
			if _, exists := out[name]; exists {
				return nil, errors.New("duplicate_key")
			}
			value, err := jsonValue(d, depth+1)
			if err != nil {
				return nil, err
			}
			out[name] = value
		}
		end, err := d.Token()
		if err != nil || end != json.Delim('}') {
			return nil, errors.New("protocol_invalid")
		}
		return out, nil
	case '[':
		out := []any{}
		for d.More() {
			value, err := jsonValue(d, depth+1)
			if err != nil {
				return nil, err
			}
			out = append(out, value)
		}
		end, err := d.Token()
		if err != nil || end != json.Delim(']') {
			return nil, errors.New("protocol_invalid")
		}
		return out, nil
	default:
		return nil, errors.New("protocol_invalid")
	}
}

func readLine(r *bufio.Reader) (map[string]any, error) {
	line, err := r.ReadSlice('\n')
	if err == io.EOF && len(line) == 0 {
		return nil, io.EOF
	}
	if err != nil || len(line) > maxLine || !utf8.Valid(line) {
		return nil, errors.New("protocol_limit")
	}
	d := json.NewDecoder(bytes.NewReader(line))
	d.UseNumber()
	v, err := jsonValue(d, 0)
	if err != nil {
		return nil, errors.New("protocol_invalid")
	}
	if _, err = d.Token(); err != io.EOF {
		return nil, errors.New("protocol_invalid")
	}
	object, ok := v.(map[string]any)
	if !ok {
		return nil, errors.New("protocol_invalid")
	}
	return object, nil
}

func fields(m map[string]any, names ...string) bool {
	if len(m) != len(names) {
		return false
	}
	for _, name := range names {
		if _, ok := m[name]; !ok {
			return false
		}
	}
	return true
}
func integer(v any) (int64, bool) {
	n, ok := v.(json.Number)
	if !ok {
		return 0, false
	}
	i, err := strconv.ParseInt(string(n), 10, 64)
	return i, err == nil
}

func parseConfig(m map[string]any) (configuration, error) {
	c := configuration{}
	if !fields(m, "local_dir", "prompt", "revision", "source_revision", "max_length", "threads") || !reflect.DeepEqual(m["prompt"], prompt) {
		return c, errors.New("initialization_invalid")
	}
	var ok bool
	c.LocalDir, ok = m["local_dir"].(string)
	if !ok || !filepath.IsAbs(c.LocalDir) || strings.IndexByte(c.LocalDir, 0) >= 0 {
		return c, errors.New("initialization_invalid")
	}
	c.Revision, ok = m["revision"].(string)
	if !ok || c.Revision != backboneRevision {
		return c, errors.New("initialization_invalid")
	}
	c.SourceRevision, ok = m["source_revision"].(string)
	if !ok || c.SourceRevision != sourceRevision {
		return c, errors.New("initialization_invalid")
	}
	n, valid := integer(m["max_length"])
	if !valid || n < 1 || n > 4096 {
		return c, errors.New("initialization_invalid")
	}
	c.MaxLength = int(n)
	n, valid = integer(m["threads"])
	if !valid || n < 1 || n > 4 {
		return c, errors.New("initialization_invalid")
	}
	c.Threads = int(n)
	return c, nil
}

func parseInput(v any) (choiceInput, error) {
	result := choiceInput{}
	m, ok := v.(map[string]any)
	if !ok || !fields(m, "context", "question", "options") {
		return result, errors.New("input_invalid")
	}
	result.Context, ok = m["context"].(string)
	if !ok {
		return result, errors.New("input_invalid")
	}
	result.Question, ok = m["question"].(string)
	if !ok || strings.TrimSpace(result.Question) == "" {
		return result, errors.New("input_invalid")
	}
	options, ok := m["options"].([]any)
	if !ok || len(options) < 2 || len(options) > 20 {
		return result, errors.New("input_invalid")
	}
	ids, descriptions := map[string]bool{}, map[string]bool{}
	for _, value := range options {
		o, ok := value.(map[string]any)
		if !ok || !fields(o, "id", "description") {
			return result, errors.New("input_invalid")
		}
		id, a := o["id"].(string)
		description, b := o["description"].(string)
		if !a || !b || strings.TrimSpace(id) == "" || strings.TrimSpace(description) == "" || ids[id] || descriptions[description] {
			return result, errors.New("input_invalid")
		}
		ids[id], descriptions[description] = true, true
		result.Options = append(result.Options, option{id, description})
	}
	return result, nil
}

// Match Python ensure_ascii=False, sort_keys=True for this string-only contract.
// encoding/json always escapes U+2028/U+2029; those are literal in Python.
func quoteText(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"', '\\':
			b.WriteByte('\\')
			b.WriteRune(r)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		default:
			if r < 32 {
				b.WriteString(`\u00`)
				b.WriteString(hex.EncodeToString([]byte{byte(r)}))
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
	return b.String()
}
func canonicalInput(v choiceInput) []byte {
	var b strings.Builder
	b.WriteString(`{"context":`)
	b.WriteString(quoteText(v.Context))
	b.WriteString(`,"options":[`)
	for i, o := range v.Options {
		if i > 0 {
			b.WriteByte(',')
		}
		b.WriteString(`{"description":`)
		b.WriteString(quoteText(o.Description))
		b.WriteString(`,"id":`)
		b.WriteString(quoteText(o.ID))
		b.WriteByte('}')
	}
	b.WriteString(`],"question":`)
	b.WriteString(quoteText(v.Question))
	b.WriteByte('}')
	return []byte(b.String())
}
func digest(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func rssMB() float64 {
	var usage syscall.Rusage
	if syscall.Getrusage(syscall.RUSAGE_SELF, &usage) != nil {
		return 0
	}
	return float64(usage.Maxrss) / 1024
}
func elapsed(t time.Time) float64 { return float64(time.Since(t)) / float64(time.Millisecond) }
func failed(code string) envelope { return envelope{Status: "error", Error: code} }

func (w *worker) predict(v choiceInput) envelope {
	start := time.Now()
	q := indecis.OpenQuestion{Name: "answer", Kind: indecis.Choice, Instructions: v.Question}
	fullTexts := []string{v.Context}
	ids := make([]string, len(v.Options))
	for i, o := range v.Options {
		// The identifier remains solely in ids; upstream reads natural language.
		q.Options = append(q.Options, indecis.Candidate{Name: o.Description})
		// DecideOpen prepends Instructions to Description, then CandidateContext
		// concatenates Name and Description. With an empty Description this is:
		fullTexts = append(fullTexts, indecis.CandidateContext(indecis.Candidate{Name: o.Description, Description: v.Question}))
		ids[i] = o.ID
	}
	fullIDs := make([][]int32, len(fullTexts))
	lengths := make([]int, len(fullTexts))
	total, maximum := 0, 0
	for i, text := range fullTexts {
		fullIDs[i] = w.tokenizer.Encode(text)
		lengths[i] = len(fullIDs[i])
		total += lengths[i]
		maximum = max(maximum, lengths[i])
	}
	raw := map[string]any{
		"native_result": nil, "ordered_ids": ids, "input_sha256": digest(canonicalInput(v)), "probabilities": nil,
		"encoding_info":    map[string]any{"tokens": maximum, "stateTruncated": false, "optionsTruncated": false},
		"token_components": map[string]any{"context_tokens": lengths[0], "option_tokens": lengths[1:], "total_tokens": total, "max_sequence_tokens": maximum},
		"inference_ms":     nil, "forward_executed": false,
	}
	if maximum > w.maxLength {
		raw["decision_ms"], raw["rss_mb"] = elapsed(start), rssMB()
		code := "indecis_option_overflow"
		if lengths[0] > w.maxLength {
			code = "indecis_context_overflow"
		}
		return envelope{Status: "unsupported", Error: code, Raw: raw}
	}
	for i, text := range fullTexts {
		actual, err := w.engine.TokenIDs(indecis.Input{Text: text})
		if err != nil || !slices.Equal(actual, fullIDs[i]) {
			return failed("indecis_encoding_mismatch")
		}
	}
	inferenceStart := time.Now()
	native, err := w.engine.DecideOpen(context.Background(), []indecis.OpenQuestion{q}, v.Context)
	inferenceMS := elapsed(inferenceStart)
	if err != nil {
		return failed("indecis_inference_failed")
	} // Forward state unknown; no fabricated audit.
	if len(native) != 1 || len(native[0]) != 1 {
		return failed("indecis_output_invalid")
	}
	a, found := native[0]["answer"]
	if !found || a.Kind != indecis.Choice || a.Question != "answer" || len(a.Probs) != len(v.Options) {
		return failed("indecis_output_invalid")
	}
	probabilities := make([]float64, len(v.Options))
	sum := 0.0
	winner := -1
	for i, o := range v.Options {
		p, exists := a.Probs[o.Description]
		if !exists || math.IsNaN(p) || math.IsInf(p, 0) || p < 0 || p > 1 {
			return failed("indecis_output_invalid")
		}
		probabilities[i] = p
		sum += p
		if o.Description == a.Choice {
			winner = i
		}
	}
	if winner < 0 || math.Abs(sum-1) > 1e-6 || math.IsNaN(a.Confidence) || math.IsInf(a.Confidence, 0) || a.Confidence < 0 || a.Confidence > 1 || math.Abs(a.Confidence-probabilities[winner]) > 1e-12 || math.IsNaN(a.Score) || math.IsInf(a.Score, 0) || a.Score < -1.00001 || a.Score > 1.00001 || math.IsNaN(a.Margin) || math.IsInf(a.Margin, 0) || a.Margin < 0 || a.Margin > 1 {
		return failed("indecis_output_invalid")
	}
	for _, p := range probabilities {
		if p > probabilities[winner] {
			return failed("indecis_output_invalid")
		}
	}
	raw["native_result"], raw["probabilities"], raw["forward_executed"], raw["inference_ms"] = a, a.Probs, true, inferenceMS
	raw["decision_ms"], raw["rss_mb"] = elapsed(start), rssMB()
	return envelope{Status: "ok", Output: map[string]string{"choice_id": v.Options[winner].ID}, Raw: raw}
}

func initialize(c configuration) (*worker, map[string]any, error) {
	start := time.Now()
	if runtime.GOOS != "linux" {
		return nil, nil, errors.New("runtime_invalid")
	}
	if _, err := os.Lstat(filepath.Join(c.LocalDir, "indecis.json")); !os.IsNotExist(err) {
		return nil, nil, errors.New("trained_model_forbidden")
	}
	for _, name := range []string{"config.json", "model.safetensors", "tokenizer.json"} {
		info, err := os.Lstat(filepath.Join(c.LocalDir, name))
		if err != nil || !info.Mode().IsRegular() {
			return nil, nil, errors.New("model_missing")
		}
	}
	runtime.GOMAXPROCS(c.Threads)
	tok, err := tokenizer.LoadShared(filepath.Join(c.LocalDir, "tokenizer.json"))
	if err != nil {
		return nil, nil, err
	}
	// No WithInt8, WithEmbedCache, WithPairs or training: raw backbone only.
	model, err := indecis.Open(c.LocalDir, indecis.WithMaxLen(c.MaxLength), indecis.WithThreads(c.Threads))
	if err != nil {
		return nil, nil, err
	}
	if model.Info().Steps != 0 || len(model.Info().TrainPrior) != 0 || model.Paired() {
		return nil, nil, errors.New("trained_model_forbidden")
	}
	executable, err := os.Executable()
	if err != nil {
		return nil, nil, err
	}
	f, err := os.Open(executable)
	if err != nil {
		return nil, nil, err
	}
	h := sha256.New()
	_, err = io.Copy(h, f)
	closeErr := f.Close()
	if err != nil || closeErr != nil {
		return nil, nil, errors.New("binary_hash_failed")
	}
	ready := map[string]any{"status": "ready", "runtime": map[string]any{"go": runtime.Version(), "goos": runtime.GOOS, "goarch": runtime.GOARCH, "indecis_revision": sourceRevision, "backbone_revision": c.Revision}, "binary_sha256": hex.EncodeToString(h.Sum(nil)), "load_ms": elapsed(start), "rss_mb": rssMB()}
	return &worker{model, tok, c.MaxLength}, ready, nil
}

func emit(out io.Writer, value any) error {
	data, err := json.Marshal(value)
	if err != nil || len(data)+1 > maxLine {
		return errors.New("protocol_limit")
	}
	data = append(data, '\n')
	for len(data) > 0 {
		n, err := out.Write(data)
		if err != nil || n == 0 {
			return errors.New("protocol_write_failed")
		}
		data = data[n:]
	}
	return nil
}

func serve(in io.Reader, out io.Writer) (code int) {
	defer func() {
		if recover() != nil {
			_ = emit(out, map[string]any{"status": "error", "error": "indecis_worker_failed"})
			code = 1
		}
	}()
	r := bufio.NewReaderSize(in, maxLine+1)
	message, err := readLine(r)
	if err != nil || !fields(message, "op", "config") || message["op"] != "initialize" {
		_ = emit(out, map[string]any{"status": "error", "error": "indecis_initialization_invalid"})
		return 1
	}
	config, ok := message["config"].(map[string]any)
	if !ok {
		_ = emit(out, map[string]any{"status": "error", "error": "indecis_initialization_invalid"})
		return 1
	}
	c, err := parseConfig(config)
	if err != nil {
		_ = emit(out, map[string]any{"status": "error", "error": "indecis_initialization_invalid"})
		return 1
	}
	w, ready, err := initialize(c)
	if err != nil {
		_ = emit(out, map[string]any{"status": "error", "error": "indecis_initialization_failed"})
		return 1
	}
	if emit(out, ready) != nil {
		return 1
	}
	var previous int64
	for {
		message, err := readLine(r)
		if err == io.EOF {
			return 0
		}
		if err != nil {
			_ = emit(out, map[string]any{"status": "error", "error": "indecis_protocol_invalid"})
			return 1
		}
		sequence, valid := integer(message["sequence"])
		if !fields(message, "op", "sequence", "input") || message["op"] != "predict" || !valid || sequence <= previous || sequence < 1 {
			_ = emit(out, map[string]any{"status": "error", "error": "indecis_protocol_invalid"})
			return 1
		}
		previous = sequence
		input, err := parseInput(message["input"])
		result := failed("indecis_input_invalid")
		if err == nil {
			result = w.predict(input)
		}
		response := map[string]any{"sequence": sequence, "status": result.Status, "output": result.Output, "error": result.Error, "raw_output": result.Raw}
		if emit(out, response) != nil {
			_ = emit(out, map[string]any{"sequence": sequence, "status": "error", "output": nil, "error": "indecis_output_limit", "raw_output": nil})
			return 1
		}
	}
}

func main() {
	// Isolate protocol stdout from accidental output or panic details upstream.
	fd, err := syscall.Dup(int(os.Stdout.Fd()))
	if err != nil {
		os.Exit(1)
	}
	protocol := os.NewFile(uintptr(fd), "protocol")
	sink, err := os.OpenFile(os.DevNull, os.O_WRONLY, 0)
	if err != nil {
		os.Exit(1)
	}
	if syscall.Dup2(int(sink.Fd()), int(os.Stdout.Fd())) != nil || syscall.Dup2(int(sink.Fd()), int(os.Stderr.Fd())) != nil {
		os.Exit(1)
	}
	_ = sink.Close()
	code := serve(os.Stdin, protocol)
	_ = protocol.Close()
	os.Exit(code)
}
