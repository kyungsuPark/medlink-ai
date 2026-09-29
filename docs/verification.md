# Verification record

검증일: 2026-09-29. Windows, Python 3.12.14에서 실행했습니다.

| 항목 | 결과 | 의미 / 제한 |
|---|---|---|
| 단위·API 테스트 | **35 passed** | 데이터 검증, 적재 원자성/idempotence, CRP 계산, 시간·입원·단위 경계, 요청 검증 |
| PostgreSQL 통합 테스트 | **7 skipped** | 현재 PC에 Docker/테스트 PostgreSQL 실행 환경 없음 |
| 실제 모델 smoke test | **다운로드 단계 실패** | Hugging Face 모델 CDN의 TLS 인증서 신뢰 오류; 추론 단계에 도달하지 못함 |
| 실제 모델 + PostgreSQL 평가 | **미실행** | 모델 다운로드와 PostgreSQL이 모두 필요 |
| Ruff 정적 검사 | **통과** | 코드 오류·import·스타일 검사 |
| Ruff format | **적용** | 전체 코드 정리 |
| Python compileall | **통과** | 소스와 테스트 문법 검사 |
| 합성 데이터 재생성 비교 | **통과** | 저장 JSON과 생성 함수의 검증된 내용 일치 |
| Compose/CI YAML 파싱 | **통과** | 문법 파싱만 확인; Docker 실행 성공을 의미하지 않음 |
| UTF-8 텍스트 검사 | **통과** | 한국어 파일 decode 및 replacement character 검사 |
| Docker 이미지 빌드/API 통합 기동 | **미실행** | Docker CLI 없음 |
| GitHub Actions | **설정 작성, 실행 미확인** | 원격 저장소 게시 전 |

로컬 검사 명령:

```bash
pytest -q -m "not semantic" --junitxml=reports/local-tests.xml
ruff check .
ruff format --check .
python -m compileall -q src tests
```

테스트 결과의 `7 skipped`는 통과로 집계하지 않았습니다. 의미 검색 테스트 두 개는 위 명령에서 제외됩니다. 별도로 실행한 실제 모델 smoke test는 외부 모델 다운로드 단계에서 실패했습니다. 의미 검색의 Recall/MRR 값은 아직 측정하지 않았으며 예상값을 측정값처럼 제시하지 않았습니다.

모델 다운로드는 기본 방식, 일반 HTTPS 방식, Windows 신뢰 저장소 활용 방식으로 확인했으며 인증서 오류가 지속됐습니다. TLS 검증을 끄지 않았습니다. 신뢰할 수 있는 CA 설정과 Hugging Face 모델 CDN 접근이 가능한 환경에서 다시 실행해야 합니다. 애플리케이션 코드에 이 PC의 인증서 설정을 포함하지 않았습니다.

현재 의존성 조합에서 Starlette TestClient의 httpx 사용에 대한 deprecation warning 한 건이 발생했습니다. 테스트 실패는 아니며 추후 TestClient 의존성 업데이트 시 정리할 항목입니다.

## 다음 환경에서 확인할 항목

```bash
docker compose --profile test run --build --rm tests
docker compose up --build -d api
docker compose exec api medlink evaluate
```

통합 테스트와 실제 평가가 끝나면 이 문서를 실제 결과로 갱신하고 `evaluation.json`을 포트폴리오에 포함하세요. 현재 코드의 의미 검색 목표(Recall@k ≥ 0.7, MRR ≥ 0.8)는 개발 목표이며 검증 완료 수치가 아닙니다.
