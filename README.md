# MedLink AI — Clinical AI Integration Platform

Legacy HIS의 검사 결과와 진료기록을 연결해 **환자 탐색 결과를 원본 근거와 함께 반환하는** FDE 포트폴리오 MVP입니다. 실제 환자 정보는 사용하지 않습니다.

입원정보와 검사결과는 SQL로 정확하게 필터링하고, 기록의 의미는 다국어 임베딩과 pgvector로 검색합니다. Hybrid는 SQL 조건을 만족하는 **동일 입원 건 안에서** 기록을 검색합니다. LLM의 임의 SQL 생성, 진단, 자유형 Agent, AWS 배포는 MVP 범위에서 제외했습니다.

## 빠른 실행

필수: Docker Engine 또는 Docker Desktop과 Compose v2. 최초 실행에는 패키지와 Hugging Face 모델 다운로드를 위한 인터넷, 여유 메모리 4GB 이상과 수 GB 디스크 공간을 권장합니다. CPU 전용입니다.

```bash
docker compose up --build -d api
docker compose logs -f init
```

`init`이 스키마 생성 → 합성 데이터 검증 → 정규화 → 임베딩 적재를 완료하면 API가 시작됩니다. 모델 다운로드 시간은 네트워크 환경에 따라 달라집니다. `init`은 성공 시 종료되는 서비스입니다.

- API 데모: [Swagger UI](http://localhost:8000/docs)
- 준비 상태: [Readiness](http://localhost:8000/health/ready)
- 프로세스 상태: [Liveness](http://localhost:8000/health/live)

```bash
docker compose ps -a
docker compose logs init api
docker compose stop
```

DB와 모델은 named volume에 유지됩니다. 같은 데이터와 모델로 seed를 다시 실행하면 `unchanged`를 반환합니다. 다른 데이터셋이나 모델을 같은 DB에 덮어쓰지 않습니다. 별도 Compose 프로젝트 이름(`docker compose -p medlink-next ...`)을 사용하면 새 volume을 가진 독립 데모를 만들 수 있습니다. 기존 프로젝트가 실행 중이면 먼저 중지해 포트 충돌을 피하세요.

## 3분 데모

데이터의 고정 조회 기준은 **2026-09-28 12:00 UTC**입니다. 재현 데모에서는 반드시 `as_of`를 전달하세요. 생략하면 현재 시각을 사용하므로 오래된 샘플이 검색되지 않을 수 있습니다.

Swagger에서 아래 순서대로 실행합니다. Bash에서는 `curl`, PowerShell에서는 `curl.exe`와 JSON 파일 또는 Swagger를 사용하세요.

**1. Structured — 최근 CRP 상승 환자**

```bash
curl -X POST http://localhost:8000/search/structured \
  -H 'Content-Type: application/json' \
  -d '{"as_of":"2026-09-28T12:00:00Z","lookback_hours":72}'
```

기대 순서: `P001`, `P006`, `P003`. 상승량은 각각 20, 20, 10 mg/L입니다. 응답에 이전/최근 검사 ID, 수치, 채혈 시각, 확정 시각, 원본 단위가 포함됩니다. P006의 원본 `3 mg/dL`은 `30 mg/L`로 정규화됩니다.

**2. Vector — 감염 관련 기록 탐색**

```json
{
  "as_of": "2026-09-28T12:00:00Z",
  "query": "감염 의심 발열 항생제 치료",
  "lookback_hours": 72,
  "top_k": 3
}
```

`POST /search/vector`에 전달합니다. 현재 입원 건의 최근 기록에서 의미상 가까운 기록을 검색하고, 입원 건당 가장 가까운 청크 하나와 기록 ID/발췌문/유사도를 반환합니다. 정답 라벨은 P001/P002/P006이지만 실제 순위와 점수는 모델 평가 결과로 확인해야 합니다.

**3. Hybrid — CRP 상승 + 감염 관련 기록 탐색**

동일 본문에 `"top_k": 2`를 설정해 `POST /search/hybrid`로 실행합니다. SQL 조건으로 A001/A003/A006을 먼저 제한하고, 그 안에서 의미 검색합니다. P001/P006은 기대 결과이며 각 결과의 `crp`와 `evidence`를 함께 확인합니다. 전체 기록에서 먼저 top-k를 뽑은 뒤 SQL 필터를 적용하는 방식에서 생기는 누락을 피했습니다.

`patient_id: "P001"`, `note_kind: "consult"`, `min_similarity`로 범위를 좁힐 수 있습니다. `min_delta_mg_l`은 Structured/Hybrid의 엄격한 초과(`>`) 조건입니다. Vector에서는 CRP 조건을 적용하지 않습니다. `min_similarity`는 기본 0이며 임상적 판정 기준이 아닙니다. 유사도 검색은 감염의 부정 표현도 반환할 수 있으므로 원문 근거를 확인하는 검색 도구로 설계했습니다.

## 테스트와 평가

Docker 통합 테스트는 별도 임시 PostgreSQL을 사용하며 데모 DB를 변경하지 않습니다. 고정 테스트 벡터를 사용하므로 모델 다운로드 없이 SQL, pgvector 연산, 필터 결합, API 응답을 검증합니다.

```bash
docker compose --profile test run --build --rm tests
```

실제 모델 기반 평가:

```bash
docker compose exec api medlink evaluate
docker compose cp api:/app/reports/evaluation.json ./evaluation.json
```

8개 golden case의 실제/기대 환자, Precision@k, Recall@k, reciprocal rank, 응답 시간을 기록합니다. 의미 검색의 평균 Recall@k와 MRR을 별도로 집계합니다. 이 소규모 합성 평가가 임상적 유효성을 입증하지는 않습니다.

GitHub Actions는 push/PR마다 코드 검사, 단위/API/실제 PostgreSQL 통합 테스트, Docker 이미지 빌드를 실행하도록 구성했습니다. Actions의 `workflow_dispatch`에서 `semantic=true`를 선택하면 실제 모델 평가도 실행합니다. CI 실행 결과는 저장소에 게시한 후 확인해야 합니다.

로컬 Python 개발(Python 3.12 권장):

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
pytest -q -m "not integration and not semantic"
ruff check .
ruff format --check .
```

로컬에서 실제 임베딩까지 실행하려면:

```bash
python -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-embeddings.lock
docker compose up -d db
# .env.example을 .env로 복사 (기본 로컬 개발 설정)
medlink init-db
medlink seed
uvicorn medlink.api:app --reload
```

`TEST_DATABASE_URL`을 별도 테스트 PostgreSQL로 설정하면 `pytest -m "not semantic"`이 통합 테스트까지 실행합니다. `RUN_SEMANTIC_TESTS=1`이면 실제 모델 테스트도 실행 가능합니다. DB가 없는 환경의 skip은 통합 테스트 성공을 의미하지 않습니다.

## 저장소 구조

```text
src/medlink/
  api.py           # 검증된 요청, 검색 응답, health endpoints
  ingest.py        # Legacy 컬럼 매핑, 무결성 검증, 원자적 적재
  sample.py        # 결정론적 합성 HIS 데이터 생성
  models.py        # Patient / Encounter / Lab / Note / Chunk
  retrieval.py     # SQL window function + pgvector cosine search
  embeddings.py    # 다국어 SentenceTransformer, 모델 공간 검증
  evaluation.py    # 실제 retrieval 경로를 통한 golden case 평가
  cli.py           # init-db / generate / seed / evaluate
data/              # 합성 export와 수작업 relevance labels
tests/             # 단위, API, PostgreSQL 통합, 실제 모델 테스트
docs/              # 아키텍처, 데이터 계약, 의사결정, 1주 계획, 검증 기록
.github/workflows/ # CI
```

## 설계의 핵심

- Oracle 스타일 원본 컬럼을 typed contract로 받아 정규화합니다. 환자·입원 키와 출처를 유지합니다.
- 검사 수치와 시간 조건은 SQL이 처리하고, 텍스트만 임베딩합니다.
- 작은 데이터셋에서는 pgvector exact search를 사용합니다. 근사 검색 인덱스 운영은 확장 단계로 미룹니다.
- 질의 시점, 입원 범위, 검사 확정 시점과 두 결과의 비교 규칙을 명시합니다.
- 데이터 오류는 전체 export를 거부하며, 실패 중 일부만 적재되는 일을 방지합니다.
- 검색 API는 읽기만 수행하며 임의 SQL이나 HIS 쓰기 경로가 없습니다.

[아키텍처](docs/architecture.md) · [데이터 계약](docs/data-contract.md) · [기술 결정](docs/decisions.md) · [1주 진행 계획](docs/one-week-plan.md) · [검증 상태](docs/verification.md)

## 범위와 배포 제한

합성 데이터 12명/13개 입원 건을 이용하는 로컬 포트폴리오입니다. 인증, 테넌트 격리, 병원 권한 체계, PHI 처리, CDC, 원본 수정/삭제 전파, 의료 성능 검증은 구현하지 않았습니다. 기본 비밀번호는 로컬 전용이며 포트는 loopback에 바인딩했습니다. 현재 구성을 인터넷에 직접 노출하지 마세요. 운영 도입 시 별도 인증과 DB 읽기 전용 역할 등이 필요합니다.

초기 스키마는 `create_all`로 생성합니다. 버전이 바뀐 기존 DB를 자동 마이그레이션하지 않습니다. 모델 이름/리비전이 바뀌면 전체 재임베딩이 필요합니다. 기본 `EMBEDDING_REVISION`은 모델 commit SHA로 고정했습니다. 모델을 바꿀 때는 고정된 새 리비전과 새 데이터베이스를 사용하세요.

GitHub에 올릴 프로젝트 루트는 이 README가 있는 `medlink-ai/`입니다. 상위 ChatGPT 동기화 폴더와 `sources/`는 포함하지 않습니다. 원격 저장소 생성/업로드는 이 산출물에 포함하지 않았습니다.

참고한 공식 문서: [pgvector Python/SQLAlchemy](https://github.com/pgvector/pgvector-python), [SentenceTransformer API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html), [다국어 모델 카드](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2).
