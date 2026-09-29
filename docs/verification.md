# Verification record

검증일: 2026-09-29. 로컬 Windows와 GitHub Actions의 Ubuntu/PostgreSQL 환경에서 확인했습니다.

| 항목 | 결과 | 의미 / 제한 |
|---|---|---|
| 로컬 단위·API 테스트 | **35 passed** | 데이터 검증, 적재 원자성, CRP 계산, 시간·입원·단위 경계, 요청 검증 |
| GitHub Actions 단위·PostgreSQL 통합 테스트 | **42 passed, 0 skipped** | 실제 PostgreSQL/pgvector 서비스에서 7개 통합 테스트 포함 |
| 실제 모델 smoke test | **GitHub Actions 통과** | 고정 리비전의 다국어 모델을 내려받아 한국어/영어 임베딩 확인 |
| 실제 모델 + PostgreSQL 평가 | **GitHub Actions 통과** | 8개 합성 golden case 전부 기대 환자 집합 일치 |
| Ruff 정적 검사 | **통과** | 코드 오류·import·스타일 검사 |
| Ruff format | **적용** | 전체 코드 정리 |
| Python compileall | **통과** | 소스와 테스트 문법 검사 |
| 합성 데이터 재생성 비교 | **통과** | 저장 JSON과 생성 함수의 검증된 내용 일치 |
| Docker Compose 설정 | **GitHub Actions 통과** | `docker compose config --quiet` |
| UTF-8 텍스트 검사 | **통과** | 한국어 파일 decode 및 replacement character 검사 |
| Docker 앱 이미지 빌드 | **GitHub Actions 통과** | `docker build --target app` |
| Compose 전체 기동·API 호출 | **미실행** | 로컬 Docker CLI 없음; CI는 이미지 빌드와 PostgreSQL 통합 테스트를 각각 실행 |

로컬 검사 명령:

```bash
pytest -q -m "not semantic" --junitxml=reports/local-tests.xml
ruff check .
ruff format --check .
python -m compileall -q src tests
```

로컬에서 통합 테스트 7개는 PostgreSQL 부재로 건너뛰었으며 통과로 집계하지 않았습니다. GitHub Actions에서는 같은 테스트를 실제 PostgreSQL/pgvector에 연결해 모두 통과했습니다. 의미 검색 테스트 두 개도 별도 수동 실행에서 통과했습니다.

로컬 Windows에서는 Hugging Face 모델 CDN의 인증서 신뢰 오류로 다운로드가 실패했습니다. TLS 검증을 끄지 않았습니다. GitHub Actions에서는 같은 모델 리비전을 정상 다운로드하여 검증했습니다. 애플리케이션 코드에 이 PC의 인증서 설정을 포함하지 않았습니다.

실제 모델 평가의 합성 5개 의미 검색 case에서 macro Recall@k와 MRR은 각각 **1.0**입니다. 전체 8개 case는 [결과 JSON](evaluation-results.json)에 기록했습니다. 작은 수작업 라벨이므로 임상적 유효성이나 부정문 처리 성능을 주장하지 않습니다. 실행 기록: [GitHub Actions](https://github.com/kyungsuPark/medlink-ai/actions/runs/36534028852).

현재 의존성 조합에서 Starlette TestClient의 httpx 사용에 대한 deprecation warning 한 건이 발생했습니다. 테스트 실패는 아니며 추후 TestClient 의존성 업데이트 시 정리할 항목입니다.

## 아직 확인할 항목

```bash
docker compose up --build -d api
docker compose exec api medlink evaluate
```

Compose 서비스 전체 기동과 실제 HTTP 호출은 아직 확인하지 않았습니다. 이미지 빌드, PostgreSQL 통합 테스트, 모델 평가의 성공과는 별도의 검증 항목입니다.
