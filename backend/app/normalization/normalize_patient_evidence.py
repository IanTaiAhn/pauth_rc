def normalize_patient_evidence(evidence: dict) -> dict:
    return {
        "diagnoses": evidence.get("diagnosis", []),
        "symptom_duration_weeks": evidence.get("symptom_duration_weeks"),
        "pt_completed_weeks": evidence.get("conservative_therapy", {})
                                      .get("physical_therapy", {})
                                      .get("completed_weeks"),
        "nsaid_trial": evidence.get("conservative_therapy", {})
                               .get("nsaids", {})
                               .get("trialed"),
        "nsaid_failed": evidence.get("conservative_therapy", {})
                                .get("nsaids", {})
                                .get("outcome") == "no relief",
        "mri_done_months_ago": evidence.get("imaging", {})
                                       .get("mri", {})
                                       .get("months_ago"),
    }
