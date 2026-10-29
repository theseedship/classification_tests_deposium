"""Separate synthetic physics choices; exact rational oracles, never model labels.

All laws/assumptions are given in the input. This finite fixture set measures
choice reasoning, not general physics knowledge or free-form derivations.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
import hashlib
import json
from pathlib import Path

VERSION = 'deposium.physics-oracles/v1'
RELATED = ['mcps.evidence-attribution', 'turbov3.rerank']


def solve(kind, params):
    """Compute the target without reading options, IDs or reference annotations."""
    p = {key: Fraction(value) for key, value in params.items()}
    if kind == 'uniform-distance': return p['v']*p['t']
    if kind == 'accelerated-velocity': return p['v0']+p['a']*p['t']
    if kind == 'accelerated-distance': return p['v0']*p['t']+p['a']*p['t']**2/2
    if kind == 'opposed-forces': return (p['forward']-p['backward'])/p['m']
    if kind == 'kinetic-energy': return p['m']*p['v']**2/2
    if kind == 'potential-energy': return p['m']*p['g']*p['h']
    if kind == 'lift-efficiency': return p['m']*p['g']*p['h']/p['efficiency']
    if kind == 'inelastic-collision': return (p['m1']*p['v1']+p['m2']*p['v2'])/(p['m1']+p['m2'])
    if kind == 'spring-energy': return p['k']*p['x']**2/2
    if kind == 'series-current': return p['u']/(p['r1']+p['r2'])
    if kind == 'parallel-resistance': return p['r1']*p['r2']/(p['r1']+p['r2'])
    if kind == 'electrical-power': return p['u']*p['i']
    if kind == 'joule-energy': return p['r']*p['i']**2*p['t']
    if kind == 'capacitor-energy': return p['c']*p['u']**2/2
    if kind == 'wave-speed': return p['f']*p['wavelength']
    if kind == 'period': return 1/p['f']
    if kind == 'echo-distance': return p['speed']*p['round_trip_time']/2
    if kind == 'thin-lens': return 1/(1/p['f']-1/p['object_distance'])
    if kind == 'isobaric-gas': return p['v1']*p['t2']/p['t1']
    if kind == 'heat-energy': return p['m']*p['c']*p['delta_t']
    if kind == 'thermal-mixing': return (p['m1']*p['t1']+p['m2']*p['t2'])/(p['m1']+p['m2'])
    if kind == 'hydrostatic-pressure': return p['rho']*p['g']*p['h']
    if kind == 'missing-mass':
        # Positive masses 2 and 3 are compatible with the input, but disagree.
        assert p['force']/2 != p['force']/3
        return None
    if kind == 'missing-capacity':
        # Positive specific heats 100 and 200 satisfy the same supplied facts.
        assert p['m']*100*p['delta_t'] != p['m']*200*p['delta_t']
        return None
    raise ValueError('Unknown physics oracle kind')


def _specs():
    # kind, difficulty, parameters, choices (semantic numbers), unit,
    # French context/question, English context/question.
    return [
      ('uniform-distance','D1',{'v':'12','t':'5'},['60','17','12/5','120'],'m',
       'Mouvement rectiligne uniforme : d = v*t. La vitesse vaut 12 m/s pendant 5 s.', 'Quelle distance est parcourue en m ?',
       'Uniform rectilinear motion: d = v*t. The speed is 12 m/s for 5 s.', 'What distance is travelled in m?'),
      ('accelerated-velocity','D1',{'v0':'3','a':'2','t':'4'},['11','9','14','8'],'m/s',
       'Accélération constante : v = v0 + a*t. v0 = 3 m/s, a = 2 m/s², t = 4 s.', 'Quelle est la vitesse finale en m/s ?',
       'Constant acceleration: v = v0 + a*t. v0 = 3 m/s, a = 2 m/s², t = 4 s.', 'What is the final velocity in m/s?'),
      ('accelerated-distance','D2',{'v0':'2','a':'3','t':'4'},['32','20','56','24'],'m',
       'Accélération constante : déplacement x = v0*t + a*t²/2. v0 = 2 m/s, a = 3 m/s², t = 4 s.', 'Quel est le déplacement en m ?',
       'Constant acceleration: displacement x = v0*t + a*t²/2. v0 = 2 m/s, a = 3 m/s², t = 4 s.', 'What is the displacement in m?'),
      ('opposed-forces','D2',{'forward':'18','backward':'6','m':'3'},['4','8','6','12'],'m/s²',
       'L’axe positif va vers la droite. Un bloc de 3 kg reçoit 18 N vers la droite et 6 N vers la gauche, sans autre force horizontale. F_net = m*a.', 'Quelle est son accélération signée en m/s² ?',
       'The positive axis points right. A 3 kg block receives 18 N to the right and 6 N to the left, with no other horizontal force. F_net = m*a.', 'What is its signed acceleration in m/s²?'),
      ('kinetic-energy','D1',{'m':'4','v':'3'},['18','6','12','36'],'J',
       'Énergie cinétique E = m*v²/2. La masse est de 4 kg et la vitesse de 3 m/s.', 'Quelle est l’énergie cinétique en J ?',
       'Kinetic energy E = m*v²/2. The mass is 4 kg and the speed is 3 m/s.', 'What is the kinetic energy in J?'),
      ('potential-energy','D1',{'m':'2','g':'10','h':'7'},['140','70','19','280'],'J',
       'Variation d’énergie potentielle ΔE = m*g*h. Une masse de 2 kg monte de 7 m, avec g = 10 m/s² constant.', 'Quelle est l’augmentation d’énergie potentielle en J ?',
       'Potential-energy change ΔE = m*g*h. A 2 kg mass rises by 7 m, with constant g = 10 m/s².', 'What is the potential-energy increase in J?'),
      ('lift-efficiency','D3',{'m':'3','g':'10','h':'4','efficiency':'3/4'},['160','120','90','40'],'J',
       'Un moteur soulève 3 kg de 4 m sans variation de vitesse. g = 10 m/s². Le travail utile est m*g*h. Son rendement vaut travail utile / énergie consommée = 3/4.', 'Quelle énergie est consommée en J ?',
       'A motor lifts 3 kg by 4 m without changing speed. g = 10 m/s². Useful work is m*g*h. Its efficiency is useful work / consumed energy = 3/4.', 'What energy is consumed in J?'),
      ('inelastic-collision','D3',{'m1':'2','v1':'6','m2':'4','v2':'-1'},['4/3','8/3','5/2','-4/3'],'m/s',
       'Deux chariots s’accrochent après une collision 1D, sans impulsion extérieure : (m1+m2)*v = m1*v1+m2*v2. m1 = 2 kg, v1 = +6 m/s, m2 = 4 kg, v2 = -1 m/s sur le même axe.', 'Quelle est leur vitesse commune signée en m/s ?',
       'Two carts stick after a 1D collision with no external impulse: (m1+m2)*v = m1*v1+m2*v2. m1 = 2 kg, v1 = +6 m/s, m2 = 4 kg, v2 = -1 m/s on the same axis.', 'What is their signed common velocity in m/s?'),
      ('spring-energy','D2',{'k':'200','x':'1/10'},['1','10','2','100'],'J',
       'Ressort idéal : E = k*x²/2. k = 200 N/m. L’allongement vaut 10 cm, soit 1/10 m.', 'Quelle énergie élastique est stockée en J ?',
       'Ideal spring: E = k*x²/2. k = 200 N/m. Extension is 10 cm, equal to 1/10 m.', 'What elastic energy is stored in J?'),
      ('series-current','D2',{'u':'12','r1':'2','r2':'4'},['2','6','3','18'],'A',
       'Deux résistances de 2 Ω et 4 Ω sont en série sous 12 V. R_eq = R1+R2 et I = U/R_eq.', 'Quelle est l’intensité du courant en A ?',
       'Two resistors of 2 Ω and 4 Ω are in series across 12 V. R_eq = R1+R2 and I = U/R_eq.', 'What is the current in A?'),
      ('parallel-resistance','D2',{'r1':'6','r2':'3'},['2','9','3','9/2'],'Ω',
       'Deux résistances de 6 Ω et 3 Ω sont en parallèle. On applique 1/R_eq = 1/R1 + 1/R2.', 'Quelle est la résistance équivalente en Ω ?',
       'Two resistors of 6 Ω and 3 Ω are in parallel. Apply 1/R_eq = 1/R1 + 1/R2.', 'What is the equivalent resistance in Ω?'),
      ('electrical-power','D1',{'u':'12','i':'3/2'},['18','8','9','24'],'W',
       'Puissance électrique P = U*I. U = 12 V et I = 3/2 A.', 'Quelle est la puissance en W ?',
       'Electrical power P = U*I. U = 12 V and I = 3/2 A.', 'What is the power in W?'),
      ('joule-energy','D2',{'r':'8','i':'2','t':'3'},['96','48','32','192'],'J',
       'Une résistance de 8 Ω est parcourue par un courant constant de 2 A pendant 3 s. L’énergie dissipée est E = R*I²*t.', 'Quelle énergie est dissipée en J ?',
       'A resistor of 8 Ω carries a constant current of 2 A for 3 s. Dissipated energy is E = R*I²*t.', 'What energy is dissipated in J?'),
      ('capacitor-energy','D3',{'c':'1/1000','u':'20'},['1/5','2/5','1/50','200'],'J',
       'Condensateur idéal : E = C*U²/2. Sa capacité de 1000 µF vaut 1/1000 F et sa tension vaut 20 V.', 'Quelle énergie est stockée en J ?',
       'Ideal capacitor: E = C*U²/2. Its capacitance of 1000 µF is 1/1000 F and its voltage is 20 V.', 'What energy is stored in J?'),
      ('wave-speed','D1',{'f':'50','wavelength':'3/5'},['30','250/3','50','3/250'],'m/s',
       'Une onde vérifie v = f*λ. f = 50 Hz et λ = 3/5 m.', 'Quelle est la célérité en m/s ?',
       'A wave obeys v = f*λ. f = 50 Hz and λ = 3/5 m.', 'What is the wave speed in m/s?'),
      ('period','D1',{'f':'8'},['1/8','8','1/4','16'],'s',
       'La période et la fréquence vérifient T = 1/f. La fréquence vaut 8 Hz.', 'Quelle est la période en s ?',
       'Period and frequency obey T = 1/f. The frequency is 8 Hz.', 'What is the period in s?'),
      ('echo-distance','D2',{'speed':'340','round_trip_time':'3/10'},['51','102','34','17'],'m',
       'Une impulsion sonore parcourt l’aller-retour vers une paroi en 3/10 s. Sa célérité constante est 340 m/s. La distance aller simple vaut célérité * durée aller-retour / 2.', 'À quelle distance se trouve la paroi, en m ?',
       'A sound pulse makes the round trip to a wall in 3/10 s. Its constant speed is 340 m/s. One-way distance is speed * round-trip time / 2.', 'How far away is the wall, in m?'),
      ('thin-lens','D3',{'f':'10','object_distance':'15'},['30','6','25','-30'],'cm',
       'Dans la convention positive pour objet et image réels, une lentille mince vérifie 1/f = 1/p + 1/q. f = 10 cm et p = 15 cm.', 'Quelle est la distance image q en cm ?',
       'Using positive distances for a real object and real image, a thin lens obeys 1/f = 1/p + 1/q. f = 10 cm and p = 15 cm.', 'What is image distance q in cm?'),
      ('isobaric-gas','D3',{'v1':'2','t1':'300','t2':'450'},['3','4/3','5','1'],'L',
       'Pour une quantité fixe de gaz idéal à pression constante, V/T est constant avec T en kelvins. V1 = 2 L à T1 = 300 K ; T2 = 450 K.', 'Quel est le volume final en L ?',
       'For a fixed amount of ideal gas at constant pressure, V/T is constant with T in kelvins. V1 = 2 L at T1 = 300 K; T2 = 450 K.', 'What is the final volume in L?'),
      ('heat-energy','D1',{'m':'1/2','c':'400','delta_t':'6'},['1200','2400','200','4800'],'J',
       'Sans changement de phase, Q = m*c*ΔT. m = 1/2 kg, c = 400 J/(kg*K), ΔT = 6 K.', 'Quelle chaleur est reçue en J ?',
       'With no phase change, Q = m*c*ΔT. m = 1/2 kg, c = 400 J/(kg*K), ΔT = 6 K.', 'What heat is received in J?'),
      ('thermal-mixing','D3',{'m1':'1','t1':'80','m2':'3','t2':'20'},['35','50','65','25'],'°C',
       'Deux masses d’un même liquide, sans changement de phase, ont la même capacité thermique massique constante. Système isolé, récipient négligeable : Tf = (m1*T1+m2*T2)/(m1+m2). m1 = 1 kg à 80 °C ; m2 = 3 kg à 20 °C.', 'Quelle température d’équilibre obtient-on en °C ?',
       'Two masses of the same liquid, with no phase change, have the same constant specific heat. Isolated system, negligible container: Tf = (m1*T1+m2*T2)/(m1+m2). m1 = 1 kg at 80 °C; m2 = 3 kg at 20 °C.', 'What equilibrium temperature is reached in °C?'),
      ('hydrostatic-pressure','D2',{'rho':'1000','g':'10','h':'3/2'},['15000','1500','150000','10000'],'Pa',
       'La surpression hydrostatique vaut Δp = ρ*g*h. ρ = 1000 kg/m³, g = 10 m/s² et profondeur h = 3/2 m. On demande la surpression, pas la pression absolue.', 'Quelle est la surpression en Pa ?',
       'Hydrostatic gauge pressure is Δp = ρ*g*h. ρ = 1000 kg/m³, g = 10 m/s² and depth h = 3/2 m. Gauge pressure, not absolute pressure, is requested.', 'What is the gauge pressure in Pa?'),
      ('missing-mass','D3',{'force':'12'},['6','4','12','insufficient'],'m/s²',
       'On connaît seulement la force résultante F = 12 N sur un objet de masse positive inconnue. La loi est a = F/m. Aucune autre donnée ne détermine la masse.', 'Quelle accélération peut-on déterminer en m/s² ?',
       'Only the net force F = 12 N on an object of unknown positive mass is known. The law is a = F/m. No other data determine the mass.', 'What acceleration can be determined in m/s²?'),
      ('missing-capacity','D3',{'m':'2','delta_t':'5'},['1000','2000','10','insufficient'],'J',
       'Sans changement de phase, Q = m*c*ΔT. On connaît m = 2 kg et ΔT = 5 K. La capacité thermique massique c est positive mais inconnue ; le matériau n’est pas identifié.', 'Quelle chaleur reçue peut-on déterminer en J ?',
       'With no phase change, Q = m*c*ΔT. Known values are m = 2 kg and ΔT = 5 K. Specific heat c is positive but unknown; the material is unidentified.', 'What received heat can be determined in J?'),
    ]


@lru_cache(maxsize=1)
def _index():
    result = {}
    difficulty_seen = Counter()
    for index, (kind, difficulty, params, choices, unit, fr_context, fr_question, en_context, en_question) in enumerate(_specs()):
        numeric = [None if c == 'insufficient' else Fraction(c) for c in choices]
        answer = solve(kind, params)
        if len(set(numeric)) != 4 or numeric.count(answer) != 1:
            raise ValueError('Physics choices must have one exact oracle answer')
        # Match six answers per position and language without exposing semantic IDs.
        shift = (numeric.index(answer) - index % 4) % 4
        choices = choices[shift:] + choices[:shift]
        gold = 'abcd'[index % 4]
        split = 'calibration' if difficulty_seen[difficulty] < 2 else 'test'
        difficulty_seen[difficulty] += 1
        for language, context, question in [('fr', fr_context, fr_question), ('en', en_context, en_question)]:
            options = []
            for letter, value in zip('abcd', choices):
                description = ('Information insuffisante.' if language == 'fr' else 'Insufficient information.') if value == 'insufficient' else f'{value} {unit}'
                options.append({'id': letter, 'description': description})
            visible = {'context': context, 'question': question, 'options': options}
            case_id = f'physics-{kind}-{language}'
            case = {'schema_version': 'deposium.case/v2', 'case_id': case_id,
                    'scenario_id': f'physics-{kind}', 'translation_family': f'physics-{kind}-fr-en',
                    'document_ids': [f'synthetic:physics-{kind}'], 'split': split,
                    'language': language, 'pack': 'RESEARCH', 'contract_id': 'bench.context-choice',
                    'input': visible,
                    'reference': {'assertions': [{'path': '/choice_id', 'op': 'equals', 'value': gold}],
                                  'abstention_allowed': False,
                                  'rationale': 'Exact rational result under the supplied law and assumptions; bilingual wording requires human review.'},
                    'evaluation': {'domain': 'physics', 'difficulty': difficulty, 'base_case_id': case_id,
                                   'related_contract_ids': RELATED[:], 'review': 'agent_only', 'task_type': kind,
                                   'oracle': {'kind': kind, 'version': VERSION, 'params': params,
                                              'choices': dict(zip('abcd', choices)), 'base_input': deepcopy(visible)},
                                   'length': None}}
            result[case_id] = case
    return result


def build_cases():
    return deepcopy(list(_index().values()))


def validate_oracle(case):
    """Reject altered facts, reference, translations, order, metadata or IDs."""
    try:
        expected = _index()[case['case_id']]
    except (KeyError, TypeError):
        raise ValueError('Unknown frozen physics case') from None
    if case != expected:
        raise ValueError('Physics case differs from its frozen exact-oracle definition')


def write_dataset(output):
    from .cases import validate_cases
    destination = Path(output)
    cases = build_cases()
    validate_cases(cases)
    payload = b''.join((json.dumps(c, ensure_ascii=False, sort_keys=True, allow_nan=False)+'\n').encode() for c in cases)
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'cases.jsonl').write_bytes(payload)
    manifest = {'schema_version': 'deposium.physics-dataset/v1', 'dataset_id': 'physics-choice-v1',
                'case_count': len(cases), 'family_count': 24, 'languages': ['fr', 'en'],
                'cases_sha256': hashlib.sha256(payload).hexdigest(), 'oracle_version': VERSION,
                'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'review': 'agent_only', 'human_review': 'not_performed', 'evaluation_status': 'not_run',
                'created_before_candidate_inference': True,
                'counts_by_difficulty': dict(Counter(c['evaluation']['difficulty'] for c in cases)),
                'counts_by_split': dict(Counter(c['split'] for c in cases)),
                'limitations': ['Finite elementary laws supplied in the input; not general physics qualification.',
                                '24 families; translations are correlated; no trained or human-reviewed reference.',
                                'No real document, measurement device or product component executed.',
                                'Separate new corpus with no historical candidate comparator.']}
    (destination/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
    return manifest
