package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"

	"github.com/bornholm/indecis"
)

type fakeTokens struct{}

func (fakeTokens) Encode(text string) []int32 {
	out := []int32{1}
	for _, r := range text {
		out = append(out, int32(r))
	}
	return append(out, 2)
}

type fakeEngine struct {
	tokens, decisions                  int
	mismatch, badOutput, failure, tied bool
	questions                          []indecis.OpenQuestion
	texts                              []string
}

func (e *fakeEngine) TokenIDs(in indecis.Input) ([]int32, error) {
	e.tokens++
	ids := fakeTokens{}.Encode(in.Text)
	if e.mismatch {
		ids[0] = 999
	}
	return ids, nil
}
func (e *fakeEngine) DecideOpen(_ context.Context, questions []indecis.OpenQuestion, texts ...string) ([]indecis.Decision, error) {
	e.decisions++
	e.questions, e.texts = questions, texts
	if e.failure {
		return nil, errors.New("sensitive internal diagnostic")
	}
	a, b := questions[0].Options[0].Name, questions[0].Options[1].Name
	answer := indecis.Answer{Question: "answer", Kind: indecis.Choice, Choice: b, Probs: map[string]float64{a: .1, b: .9}, Confidence: .9, Score: .7, Margin: .8}
	if e.tied {
		answer.Choice, answer.Probs, answer.Confidence, answer.Margin = a, map[string]float64{a: .5, b: .5}, .5, 0
	}
	if e.badOutput {
		answer.Choice = a
	}
	return []indecis.Decision{{"answer": answer}}, nil
}
func sample() choiceInput {
	return choiceInput{"context", "question", []option{{"PRIVATE_ID_1", "first"}, {"PRIVATE_ID_2", "second"}}}
}
func fakeWorker(e *fakeEngine, limit int) *worker { return &worker{e, fakeTokens{}, limit} }

func TestNativeCallAndMetadataIsolation(t *testing.T) {
	e := &fakeEngine{}
	v := sample()
	result := fakeWorker(e, 4096).predict(v)
	if result.Status != "ok" || result.Output.(map[string]string)["choice_id"] != "PRIVATE_ID_2" || e.decisions != 1 {
		t.Fatalf("unexpected result %+v", result)
	}
	if len(e.texts) != 1 || e.texts[0] != v.Context || e.questions[0].Instructions != v.Question {
		t.Fatal("input changed")
	}
	for i, o := range e.questions[0].Options {
		if o.Name != v.Options[i].Description || o.Description != "" || len(o.Examples) != 0 {
			t.Fatal("IDs or synthetic metadata entered options")
		}
	}
	raw := result.Raw.(map[string]any)
	components := raw["token_components"].(map[string]any)
	if components["context_tokens"] != 9 || components["max_sequence_tokens"] != 17 || components["total_tokens"] != 42 {
		t.Fatalf("wrong ragged token accounting %+v", components)
	}
	if raw["input_sha256"] != digest(canonicalInput(v)) || raw["forward_executed"] != true || raw["inference_ms"] == nil {
		t.Fatal("audit absent")
	}
}
func TestOverflowBeforeEveryNativeMethod(t *testing.T) {
	for index, mutate := range []func(*choiceInput){func(v *choiceInput) { v.Context = strings.Repeat("x", 50) }, func(v *choiceInput) { v.Options[1].Description = strings.Repeat("x", 50) }} {
		v := sample()
		mutate(&v)
		e := &fakeEngine{}
		r := fakeWorker(e, 30).predict(v)
		code := []string{"indecis_context_overflow", "indecis_option_overflow"}[index]
		if r.Status != "unsupported" || r.Error != code || e.decisions != 0 || e.tokens != 0 {
			t.Fatalf("overflow reached native engine %+v", r)
		}
		raw := r.Raw.(map[string]any)
		if raw["forward_executed"] != false || raw["inference_ms"] != nil || raw["native_result"] != nil {
			t.Fatal("invented overflow computation")
		}
	}
}
func TestEncodingMismatchDoesNotForward(t *testing.T) {
	e := &fakeEngine{mismatch: true}
	r := fakeWorker(e, 4096).predict(sample())
	if r.Status != "error" || r.Error != "indecis_encoding_mismatch" || e.decisions != 0 {
		t.Fatalf("mismatch reached forward %+v", r)
	}
}
func TestNativeErrorsStayFixedAndNonArgmaxIsRejected(t *testing.T) {
	for _, e := range []*fakeEngine{{failure: true}, {badOutput: true}} {
		r := fakeWorker(e, 4096).predict(sample())
		if r.Status != "error" || r.Raw != nil {
			t.Fatalf("native error accepted %+v", r)
		}
		b, _ := json.Marshal(r)
		if bytes.Contains(b, []byte("sensitive")) {
			t.Fatal("leaked native diagnostic")
		}
	}
}
func TestTiedDistributionUsesNativeChoiceAndOrder(t *testing.T) {
	v := sample()
	v.Options[0], v.Options[1] = v.Options[1], v.Options[0]
	e := &fakeEngine{tied: true}
	r := fakeWorker(e, 4096).predict(v)
	if r.Status != "ok" || r.Output.(map[string]string)["choice_id"] != "PRIVATE_ID_2" {
		t.Fatal("tie remapping ignored supplied order")
	}
}
func TestCanonicalUnicodeMatchesPythonFixture(t *testing.T) {
	v := choiceInput{"<>&\u2028\u2029é\n\x00", "why?", []option{{"z", "A"}, {"y", "B"}}}
	expected := "{\"context\":\"<>&\u2028\u2029é\\n\\u0000\",\"options\":[{\"description\":\"A\",\"id\":\"z\"},{\"description\":\"B\",\"id\":\"y\"}],\"question\":\"why?\"}"
	if string(canonicalInput(v)) != expected {
		t.Fatalf("canonical bytes disagree: %q", canonicalInput(v))
	}
}
func TestProtocolRejectsDuplicatesExtraJSONAndOversize(t *testing.T) {
	for _, line := range []string{"{\"x\":1,\"x\":2}\n", "{\"a\":{\"x\":1,\"x\":2}}\n", "{} {}\n", "{}", strings.Repeat(" ", maxLine) + "\n", "{\"x\":NaN}\n"} {
		if _, err := readLine(bufio.NewReaderSize(strings.NewReader(line), maxLine+1)); err == nil {
			t.Fatalf("bad protocol accepted %q", line[:min(len(line), 100)])
		}
	}
}
func TestInputRejectsAnnotationsAndDuplicates(t *testing.T) {
	for _, line := range []string{
		`{"context":"x","question":"q","options":[{"id":"a","description":"A"},{"id":"a","description":"B"}]}`,
		`{"context":"x","question":"q","options":[{"id":"a","description":"A"},{"id":"b","description":"A"}]}`,
		`{"context":"x","question":"q","options":[{"id":"a","description":"A"},{"id":"b","description":"B"}],"reference":"a"}`,
	} {
		m, err := readLine(bufio.NewReaderSize(strings.NewReader(line+"\n"), maxLine+1))
		if err != nil {
			t.Fatal(err)
		}
		if _, err = parseInput(m); err == nil {
			t.Fatal("invalid candidate contract accepted")
		}
	}
}
func TestBootstrapMissingFilesNeedsNoModelOrWeights(t *testing.T) {
	c := map[string]any{"op": "initialize", "config": map[string]any{"local_dir": t.TempDir(), "prompt": prompt, "revision": backboneRevision, "source_revision": sourceRevision, "max_length": 4096, "threads": 2}}
	b, _ := json.Marshal(c)
	b = append(b, '\n')
	var out bytes.Buffer
	if serve(bytes.NewReader(b), &out) != 1 || strings.Contains(out.String(), "ready") || !strings.Contains(out.String(), "indecis_initialization_failed") {
		t.Fatal("missing assets accepted or loaded")
	}
}
