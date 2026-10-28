# Repeated timing archive comparison

Timing cells show n/min/median/p95/max in milliseconds; RSS cells show observed n and max MiB.
Cold, warmup and measured calls are separate. Warmup never enters measured-pass quality.

## Context choice: 18 cases, 9 families

| Archive | Candidate | Phase | Calls | OK | Adapter | Decision | Inference | HTTP | RSS n/max |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| Context | gliner-2.5-multi-decide-cpu-context-v1 | cold | 3 | 3 | 3/241.204/251.574/279.909/279.909 | 3/233.986/244.020/272.262/272.262 | 3/228.477/238.683/266.133/266.133 | unobserved (n=0) | 3/2885.773 |
| Context | gliner-2.5-multi-decide-cpu-context-v1 | warmup | 15 | 15 | 15/170.210/201.652/258.822/258.822 | 15/163.372/193.864/251.805/251.805 | 15/160.928/192.301/250.158/250.158 | unobserved (n=0) | 15/2885.773 |
| Context | gliner-2.5-multi-decide-cpu-context-v1 | measured | 162 | 162 | 162/161.598/194.885/251.455/288.077 | 162/154.580/187.771/243.106/280.414 | 162/152.180/186.155/240.306/278.689 | unobserved (n=0) | 162/2885.773 |
| Context | julia-1-cpu-context-choice-v1 | cold | 3 | 3 | 3/62.346/80.325/108.369/108.369 | 3/58.094/75.755/104.287/104.287 | 3/57.985/75.645/104.182/104.182 | unobserved (n=0) | 3/1004.207 |
| Context | julia-1-cpu-context-choice-v1 | warmup | 15 | 15 | 15/51.581/57.656/86.109/86.109 | 15/47.225/53.444/81.739/81.739 | 15/47.094/53.349/81.637/81.637 | unobserved (n=0) | 15/1008.457 |
| Context | julia-1-cpu-context-choice-v1 | measured | 162 | 162 | 162/44.943/64.273/89.093/109.645 | 162/40.680/59.745/84.272/105.082 | 162/40.585/59.632/84.179/104.980 | unobserved (n=0) | 162/1015.707 |
| Jev | jev-1.13.0-api-context-v1 | cold | 3 | 3 | 3/283.026/311.505/328.204/328.204 | unobserved (n=0) | unobserved (n=0) | 3/267.131/290.366/308.481/308.481 | 0/unobserved |
| Jev | jev-1.13.0-api-context-v1 | warmup | 15 | 15 | 15/260.210/295.043/361.129/361.129 | unobserved (n=0) | unobserved (n=0) | 15/241.954/274.814/342.430/342.430 | 0/unobserved |
| Jev | jev-1.13.0-api-context-v1 | measured | 162 | 162 | 162/258.257/290.563/332.005/382.251 | unobserved (n=0) | unobserved (n=0) | 162/237.929/272.201/311.953/361.189 | 0/unobserved |
| Indecis | indecis-bekko-open-cpu-context-v1 | cold | 3 | 3 | 3/52.414/52.659/54.585/54.585 | 3/44.327/45.065/46.179/46.179 | 3/43.818/44.770/45.849/45.849 | unobserved (n=0) | 3/823.641 |
| Indecis | indecis-bekko-open-cpu-context-v1 | warmup | 15 | 15 | 15/30.408/34.125/39.601/39.601 | 15/22.831/26.012/31.849/31.849 | 15/22.567/25.749/31.652/31.652 | unobserved (n=0) | 15/836.766 |
| Indecis | indecis-bekko-open-cpu-context-v1 | measured | 162 | 162 | 162/29.261/34.125/44.321/51.642 | 162/21.548/25.989/35.389/40.324 | 162/21.489/25.928/35.299/40.256 | unobserved (n=0) | 162/960.746 |

| Archive | Candidate | Initialization ms | Reported load ms | Load RSS n/max MiB | Passed / scored calls | Passed per pass | Variable choice cases | Decision medians by launch ms |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Context | gliner-2.5-multi-decide-cpu-context-v1 | 3/10763.866/10917.359/10974.842/10974.842 | 3/10098.815/10374.665/10456.283/10456.283 | 3/2885.773 | 54/162 | 6–6/18 | 0/18 | 184.849, 187.262, 196.695 |
| Context | julia-1-cpu-context-choice-v1 | 3/11610.130/11747.730/15199.503/15199.503 | 3/11316.060/11450.505/14367.303/14367.303 | 3/923.930 | 54/162 | 6–6/18 | 0/18 | 58.188, 59.986, 60.487 |
| Jev | jev-1.13.0-api-context-v1 | 3/0.391/0.443/0.483/0.483 | unobserved (n=0) | 0/unobserved | 157/162 | 17–18/18 | 3/18 | unobserved |
| Indecis | indecis-bekko-open-cpu-context-v1 | 3/1110.055/1167.808/1218.472/1218.472 | 3/1014.295/1069.023/1107.072/1107.072 | 3/790.016 | 54/162 | 6–6/18 | 0/18 | 24.946, 25.731, 26.508 |

## Document task: 14 cases, 7 families

| Archive | Candidate | Phase | Calls | OK | Adapter | Decision | Inference | HTTP | RSS n/max |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| Historical | julia-1-cpu-document-task-v1 | cold | 3 | 3 | 3/75.383/79.882/85.084/85.084 | 3/71.536/75.751/80.402/80.402 | 3/71.471/75.674/80.327/80.327 | unobserved (n=0) | 3/996.145 |
| Historical | julia-1-cpu-document-task-v1 | warmup | 15 | 15 | 15/72.092/79.983/131.784/131.784 | 15/67.748/75.661/126.828/126.828 | 15/67.681/75.592/126.740/126.740 | unobserved (n=0) | 15/996.895 |
| Historical | julia-1-cpu-document-task-v1 | measured | 420 | 420 | 420/68.201/82.958/112.824/134.787 | 420/64.260/78.647/107.963/129.774 | 420/64.200/78.578/107.887/129.691 | unobserved (n=0) | 420/999.895 |
| Historical | mcps-document-task-resident-v1 | cold | 3 | 3 | 3/14.857/15.306/15.605/15.605 | 3/4.979/5.204/5.286/5.286 | unobserved (n=0) | unobserved (n=0) | 0/unobserved |
| Historical | mcps-document-task-resident-v1 | warmup | 15 | 15 | 15/9.423/10.579/14.381/14.381 | 15/0.112/0.352/4.637/4.637 | unobserved (n=0) | unobserved (n=0) | 0/unobserved |
| Historical | mcps-document-task-resident-v1 | measured | 420 | 420 | 420/8.146/9.645/11.975/19.125 | 420/0.036/0.085/0.260/1.212 | unobserved (n=0) | unobserved (n=0) | 0/unobserved |

| Archive | Candidate | Initialization ms | Reported load ms | Load RSS n/max MiB | Passed / scored calls | Passed per pass | Variable choice cases | Decision medians by launch ms |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Historical | julia-1-cpu-document-task-v1 | 3/10695.926/10816.798/11190.284/11190.284 | 3/10427.884/10576.247/10853.821/10853.821 | 3/926.074 | 300/420 | 10–10/14 | 0/14 | 75.704, 78.202, 84.383 |
| Historical | mcps-document-task-resident-v1 | 3/550.892/565.332/649.877/649.877 | 3/160.651/173.181/175.501/175.501 | 0/unobserved | 420/420 | 14–14/14 | 0/14 | 0.084, 0.086, 0.089 |

EOS, Noma and Laya: not measured in these archives.

These are historical local/API observations, not a new model run or product qualification.
