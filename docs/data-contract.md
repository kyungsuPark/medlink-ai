# Legacy export → AI-ready data contract

`data/legacy_his.json`은 `medlink generate`로 동일하게 재생성할 수 있습니다. 모든 내용은 직접 작성한 합성 데이터입니다. 날짜에는 반드시 UTC 또는 명시적 offset이 있어야 합니다.

| Legacy field | 정규화 목적지 | 규칙 |
|---|---|---|
| PT_NO | patients.id | P + 3~6자리 숫자, 고유 |
| PT_NM | patients.display_name | Synthetic patient 이름 |
| ADM_NO | encounters.id / 참조 키 | 모든 검사/기록은 입원 건에 귀속 |
| IN_DTM / OUT_DTM | admitted_at / discharged_at | `[입원, 퇴원)`; 퇴원 null이면 진행 중 |
| RSLT_NO | labs.id | 원본 검사 근거 ID |
| ITEM_CD | labs.code | MVP는 CRP만 허용 |
| RSLT_VAL / UNIT | labs.value / unit | mg/dL × 10 → mg/L; 원본 값·단위도 보관 |
| COLLECT_DTM | collected_at | 추세 순서를 결정하는 시각 |
| VERIFY_DTM | available_at | 조회 시점에 알려진 결과인지 판단 |
| STATUS | 적재 선택 | F 확정만 적재; P 미확정, C 취소 제외 |
| DOC_NO | notes.id | 원문과 검색 근거 ID |
| DOC_KIND | notes.kind | progress / consult |
| SIGN_DTM | notes.recorded_at | 서명된 기록이 이용 가능해진 시각 |
| BODY | notes.text / chunks.text | 공백 정리 후 80문자 청크, 12문자 overlap |

정규화 과정에서 중복 키, 연결되지 않은 외래 키, 겹치는 입원 기간, 입원 범위 밖 기록, 알 수 없는 단위, 음수/비유한 수치, 잘못된 시간 순서, 공백뿐인 문서를 거부합니다. 한 건이 잘못되면 전체 snapshot을 거부합니다.

80문자 청크는 작은 혼합 언어 데모를 위한 단순 규칙입니다. 임베딩 직전에 실제 tokenizer 길이를 검사하며 모델 한도를 초과하면 조용히 자르지 않고 실패합니다. 긴 질의는 422를 반환합니다. 문장/섹션 경계를 고려한 토큰 청킹은 다음 확장 항목입니다.

## 재현 가능한 반례

| 환자 | 검증 목적 | 기본 Structured 결과 |
|---|---|---|
| P001 | 10 → 30 mg/L, 감염 기록 | 포함 |
| P002 | 감염 기록은 있지만 50 → 20 | 제외 |
| P003 | 5 → 15, 재활 기록; 미래 감염 기록은 제외 | 포함 |
| P004 | 이미 퇴원, 검사 상승 | 제외 |
| P005 | 검사 한 개 | 제외 |
| P006 | 1 → 3 mg/dL, 폐렴 협진 | 포함 |
| P007 | 미래 결과 100은 조회 시점에서 미관측 | 제외 |
| P008 | 미확정/취소 고수치, 감염 부정 문구 | 제외 |
| P009 | 이전 입원에는 상승, 현재 입원 검사 한 개 | 제외 |
| P010 | 이미 채혈했지만 다음 날 확정된 고수치 | 제외 |
| P011 | 동일 채혈 시각 두 결과 | 제외 |
| P012 | 미래 입원 | 제외 |

결과 시각이 같은 경우 정렬은 확정 시각, ID로 결정되지만 그 두 검사는 상승 추세로 인정하지 않습니다. MVP는 원본 결과의 수정 이력이나 검사 ID별 버전 체계를 지원하지 않습니다. 실제 HIS 연계에서는 검체/오더/결과 버전 키와 correction 정책을 먼저 정의해야 합니다.

## 증분 동기화 범위

데이터셋 ID, canonical JSON SHA-256, 임베딩 모델 키를 저장합니다. 같은 snapshot과 모델 키의 재실행은 no-op입니다. 달라진 snapshot/model은 실패시키고 새 DB를 요구합니다. 이는 안전한 1회 export PoC이며 운영 CDC나 재색인 파이프라인의 대체가 아닙니다. 기본 모델은 commit SHA로 고정했습니다. 사용자가 `main`처럼 움직이는 리비전으로 변경하면 원격 모델 변경을 키만으로 감지할 수 없습니다.
