"""Reproducible, hand-designed edge cases; never copied from a real HIS."""

AS_OF = "2026-09-28T12:00:00Z"


def synthetic_export() -> dict:
    patients = [{"PT_NO": f"P{i:03}", "PT_NM": f"Synthetic patient {i:03}"} for i in range(1, 13)]
    admissions = [
        {
            "ADM_NO": f"A{i:03}",
            "PT_NO": f"P{i:03}",
            "IN_DTM": "2026-09-20T09:00:00Z",
            "OUT_DTM": None,
            "WARD_CD": "W01",
        }
        for i in range(1, 13)
    ]
    admissions[3]["OUT_DTM"] = "2026-09-28T10:00:00Z"
    admissions[11]["IN_DTM"] = "2026-09-29T09:00:00Z"
    admissions[8]["IN_DTM"] = "2026-09-28T09:00:00Z"
    admissions.append(
        {
            "ADM_NO": "A009-OLD",
            "PT_NO": "P009",
            "IN_DTM": "2026-09-23T00:00:00Z",
            "OUT_DTM": "2026-09-27T23:00:00Z",
            "WARD_CD": "W02",
        }
    )
    labs = []

    def lab(encounter, suffix, value, time, unit="mg/L", status="F", available=None):
        labs.append(
            {
                "RSLT_NO": f"L-{encounter}-{suffix}",
                "ADM_NO": encounter,
                "ITEM_CD": "CRP",
                "RSLT_VAL": value,
                "UNIT": unit,
                "COLLECT_DTM": time,
                "VERIFY_DTM": available or time,
                "STATUS": status,
            }
        )

    for i, (previous, latest) in enumerate(
        [
            (10, 30),
            (50, 20),
            (5, 15),
            (10, 50),
            (0, 8),
            (1, 3),
            (20, 10),
            (20, 10),
            (0, 9),
            (20, 10),
            (10, 30),
            (1, 8),
        ],
        start=1,
    ):
        enc = f"A{i:03}"
        previous_time = "2026-09-27T08:00:00Z"
        latest_time = "2026-09-28T08:00:00Z"
        if i == 11:
            previous_time = latest_time  # Not a trend: identical collection timestamps.
        if i == 12:
            previous_time, latest_time = "2026-09-29T10:00:00Z", "2026-09-30T08:00:00Z"
        if i == 9:
            latest_time = "2026-09-28T10:00:00Z"
        if i not in (5, 9):
            lab(enc, "1", previous, previous_time, "mg/dL" if i == 6 else "mg/L")
        lab(enc, "2", latest, latest_time, "mg/dL" if i == 6 else "mg/L")
    lab("A007", "future", 100, "2026-09-29T08:00:00Z")
    lab("A008", "pending", 100, "2026-09-28T09:00:00Z", status="P")
    lab("A008", "cancelled", 200, "2026-09-28T10:00:00Z", status="C")
    lab("A009-OLD", "1", 1, "2026-09-26T08:00:00Z")
    lab("A009-OLD", "2", 100, "2026-09-27T08:00:00Z")
    lab("A010", "late", 100, "2026-09-28T09:00:00Z", available="2026-09-29T08:00:00Z")
    bodies = [
        "감염 의심으로 발열과 오한을 평가함. 혈액 배양 검사 후 항생제 치료를 시작함.",
        "Infection with fever. Receiving antibiotics; inflammatory markers are improving.",
        "무릎 수술 후 재활 중. 보행 연습과 통증 조절을 진행하며 식사 섭취 양호함.",
        "발열과 감염으로 항생제를 투여한 뒤 상태가 호전되어 퇴원함.",
        "어지럼증 평가를 위해 입원함. 보행 시 균형을 확인하고 수분 섭취를 권고함.",
        "협진: 폐렴 의심, 발열 및 기침 지속. 배양 검사와 항생제 치료 반응을 관찰함.",
        "두통이 호전됨. 신경학적 변화 없이 안정적인 상태임.",
        "발열 없고 감염 소견 없음. 항생제 투여 계획 없음.",
        "재입원 후 수면과 식사 상태 확인. 현재 입원 검사 결과는 한 건임.",
        "피로감에 대해 경과 관찰 중. 추가 검사 결과는 아직 확정되지 않음.",
        "동일 검체 시각의 중복 검사 결과 확인이 필요함.",
        "향후 입원 건에 작성된 기록. 감염 의심으로 항생제 치료 예정.",
    ]
    documents = [
        {
            "DOC_NO": f"N{i:03}",
            "ADM_NO": f"A{i:03}",
            "DOC_KIND": "consult" if i in (1, 6) else "progress",
            "SIGN_DTM": ("2026-09-29T10:00:00Z" if i == 12 else "2026-09-28T09:30:00Z"),
            "BODY": body,
        }
        for i, body in enumerate(bodies, 1)
    ]
    documents.extend(
        [
            {
                "DOC_NO": "N009-OLD",
                "ADM_NO": "A009-OLD",
                "DOC_KIND": "consult",
                "SIGN_DTM": "2026-09-27T09:00:00Z",
                "BODY": "이전 입원 당시 감염과 발열로 항생제 치료함.",
            },
            {
                "DOC_NO": "N003-FUTURE",
                "ADM_NO": "A003",
                "DOC_KIND": "consult",
                "SIGN_DTM": "2026-09-29T09:00:00Z",
                "BODY": "다음 날 감염 의심 기록. 발열과 항생제 치료.",
            },
        ]
    )
    return {
        "dataset_id": "synthetic-his-v1",
        "synthetic": True,
        "patients": patients,
        "admissions": admissions,
        "labs": labs,
        "documents": documents,
    }
