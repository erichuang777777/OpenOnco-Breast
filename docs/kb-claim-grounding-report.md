# KB Claim-Anchor Grounding Report

_Generated_: 2026-08-03T09:31:26.891552+00:00

Audit of claim-bearing prose fields on Indication, Regimen, and BiomarkerActionability entities. Layer 1 (detection) checks whether the parent entity cites ≥1 SRC-* anchor; Layer 2 (semantic, opt-in) asks the Claude API whether each cited source plausibly supports the claim. Tracks Q4/Q5 of `docs/plans/kb_data_quality_plan_2026-04-29.md`; v1.0 target ≥90% anchor coverage.

## Top-level metrics

| Metric | Numerator | Denominator | Score |
|---|---:|---:|---:|
| Claim-bearing fields with ≥1 anchor | 3578 | 3602 | 99.3% |

## Per-entity-type breakdown

| Entity type | Total claims | Anchored | Coverage |
|---|---:|---:|---:|
| biomarker_actionability | 950 | 950 | 100.0% |
| indications | 1911 | 1911 | 100.0% |
| regimens | 741 | 717 | 96.8% |

## Detached claims (top 50 of 24)

These entities make claim-bearing assertions but cite no resolving SRC-* anchor anywhere on the entity. Each is a candidate for a Q4 remediation chunk.

| Entity | Field | Excerpt | Suggested action |
|---|---|---|---|
| `REG-BEP-GCT` (regimens) | `notes_ua` | BEP (блеоміцин + етопозид + цисплатин): стандартна 1L хіміотерапія пухлин зародкових клітин (ПЗК) яєчка. Блеоміцин (bleomycin) 30 ОД в/в дн… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-CABAZITAXEL-MCRPC` (regimens) | `notes_ua` | Кабазитаксел (cabazitaxel) 20-25 мг/м² в/в + преднізон (prednisone) 10 мг/добу перорально при мКРРП 2L. TROPIC: ЗВ ВР 0,70 проти мітоксантр… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-CABOZANTINIB-HCC` (regimens) | `notes_ua` | Кабозантиніб (cabozantinib) 60 мг перорально щоденно безперервно при ГЦК 2L (CELESTIAL, n=707): мЗВ 10,2 проти 8,0 міс. (ВР 0,76, p=0,005);… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-CARBO-PACLI-ANAL-MET` (regimens) | `notes_ua` | Карбоплатин (carboplatin) AUC 5 + паклітаксел (paclitaxel) 175 мг/м² в/в день 1 q21d при метастатичному / рецидивуючому неоперабельному ASC… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-CE-SCLC` (regimens) | `notes_ua` | Карбоплатин (carboplatin) AUC 5 + етопозид (etoposide) 100 мг/м²/добу дні 1-3 q21d × 4-6 циклів при МДрЛ без імунотерапії. Використовується… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-DAB-TRAM-ATC` (regimens) | `notes_ua` | Дабрафеніб (dabrafenib) 150 мг перорально двічі на добу + траметиніб (trametinib) 2 мг перорально щоденно при BRAF V600E ATC (ROAR, n=36): … | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-DOXORUBICIN-IFOSFAMIDE-STS` (regimens) | `notes_ua` | Доксорубіцин (doxorubicin) 75 мг/м² + іфосфамід (ifosfamide) 10 г/м² (2,5 г/м²/добу дні 1-4) + мезна (mesna, ОБОВ'ЯЗКОВА) q21d при СМТ 1L а… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-DOXORUBICIN-STS` (regimens) | `notes_ua` | Доксорубіцин (doxorubicin) 75 мг/м² в/в день 1 q21d при СМТ 1L стандарт (ЗРВ ~14-27%). Везикант — обов'язковий центральний венозний доступ.… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-EP-GCT` (regimens) | `notes_ua` | EP (етопозид (etoposide) + цисплатин (cisplatin)): варіант без блеоміцину при ПЗК. Показання: легеневий фіброз / знижений DLCO (<80%), CrCl… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-EV-MONO-UROTHELIAL` (regimens) | `notes_ua` | Енфортумаб ведотин (enfortumab vedotin) 1,25 мг/кг в/в дні 1, 8, 15 q28d при уротеліальній карциномі 2L монотерапія (EV-301, n=608): мЗВ 12… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-GEMCITABINE-DOCETAXEL-STS` (regimens) | `notes_ua` | Гемцитабін (gemcitabine) 900 мг/м² в/в (фіксована швидкість 10 мг/м²/хв КРИТИЧНО) + доцетаксел (docetaxel) 100 мг/м² дні 1 і 8 q21d при СМТ… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-NAL-IRI-5FU-LV-PDAC` (regimens) | `notes_ua` | Нал-ІРІ (nal-IRI, nanoliposomal irinotecan, ONIVYDE) 70 мг/м² (вільна основа) в/в день 1 + 5-ФУ (fluorouracil) 2400 мг/м² 46-год інфузія + … | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-NIGRO-MMC-5FU-RT` (regimens) | `notes_ua` | Протокол Ніґро (Nigro): мітоміцин-C (mitomycin-C) 10-12 мг/м² болюс дні 1 і 29 + 5-ФУ (fluorouracil) 1000 мг/м²/добу безперервна інфузія дн… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-NIVO-IPI-MESOTHELIOMA` (regimens) | `notes_ua` | Ніволумаб (nivolumab) 3 мг/кг в/в q14d + іпілімумаб (ipilimumab) 1 мг/кг в/в q6w при злоякісній плевральній мезотеліомі (МПМ) 1L (CheckMate… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-NIVOLUMAB-MONO` (regimens) | `notes_ua` | Ніволумаб (nivolumab) монотерапія: 240 мг в/в кожні 2 тижні АБО 480 мг в/в кожні 4 тижні (FDA-схвалений еквівалент). Анти-PD-1 ICI з широки… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-PAZOPANIB-STS` (regimens) | `notes_ua` | Пазопаніб (pazopanib) 800 мг перорально щоденно безперервно при СМТ 2L (PALETTE, n=369): ВБП 4,6 проти 1,6 міс. (ВР 0,31, p<0,0001), без пе… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-PEMBRO-CHEMO-TNBC-MET` (regimens) | `notes_ua` | Пембролізумаб (pembrolizumab) 200 мг + хімія (наб-паклітаксел 100 мг/м² дні 1, 8, 15 q28d АБО паклітаксел 90 мг/м² дні 1, 8, 15 q28d АБО ге… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-PEMBROLIZUMAB-MONO` (regimens) | `notes_ua` | Пембролізумаб (pembrolizumab) монотерапія: 200 мг в/в кожні 3 тижні АБО 400 мг кожні 6 тижнів (FDA-схвалений еквівалент). Анти-PD-1 ICI з п… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-PEMETREXED-CISPLATIN-MPM` (regimens) | `notes_ua` | Пеметрексед (pemetrexed) 500 мг/м² в/в день 1 + цисплатин (cisplatin) 75 мг/м² в/в день 1 q21d при злоякісній плевральній мезотеліомі (МПМ)… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-RADIUM223-MCRPC` (regimens) | `notes_ua` | Радій-223 (radium-223 dichloride, Xofigo) 55 кБк/кг в/в 1 раз на 4 тижні × 6 ін'єкцій при мКРРП з кістковими метастазами без вісцеральних м… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-RAMUCIRUMAB-HCC` (regimens) | `notes_ua` | Рамуцирумаб (ramucirumab) 8 мг/кг в/в кожні 14 днів при ГЦК 2L з АФП >=400 нг/мл (REACH-2, n=292): мЗВ 8,5 проти 7,3 міс. (ВР 0,71, p=0,019… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-REGORAFENIB-HCC` (regimens) | `notes_ua` | Регорафеніб (regorafenib) 160 мг перорально щоденно дні 1-21 q28d (3 тижні прийом / 1 тиждень відпочинок) при ГЦК 2L після сорафенібу (RESO… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-TIP-GCT-SALVAGE` (regimens) | `notes_ua` | TIP (паклітаксел (paclitaxel) 250 мг/м² 24-год безперервна інфузія день 1 + іфосфамід (ifosfamide) 1,5 г/м²/добу дні 2-6 + цисплатин (cispl… | add SRC-* anchor or downgrade to maintainer-review note |
| `REG-TOPOTECAN-SCLC-RR` (regimens) | `notes_ua` | Топотекан (topotecan) 1,5 мг/м²/добу в/в дні 1-5 q21d при рецидивуючому / рефрактерному МДрЛ. При чутливому рецидиві (CTFI >=90 днів): ЗРВ … | add SRC-* anchor or downgrade to maintainer-review note |
