Newly generated patient info fails when attempting to extract via groq llm.

patient_02_fail_insufficient_conservative.txt --> 
{
  "detail": "Error processing file: '>' not supported between instances of 'NoneType' and 'int'"
}

patient_03_exception_acute_acl
{
  "detail": "Error processing file: '>' not supported between instances of 'NoneType' and 'int'"
}

patient_05_workerscomp_exclusion
{
  "detail": "Error processing file: 1 validation error for InitialPatientExtraction\nmissing_items.0\n  Input should be a valid string [type=string_type, input_value={'name': 'symptom_duratio... of at least 3 months.'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.12/v/string_type"
}

patient_07_exception_post_surgical
{
  "detail": "Error processing file: 2 validation errors for InitialPatientExtraction\nmissing_items.0\n  Input should be a valid string [type=string_type, input_value={'name': 'symptom_duratio... of at least 3 months.'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.12/v/string_type\nmissing_items.1\n  Input should be a valid string [type=string_type, input_value={'name': 'conservative_th..., NSAIDs, injections).'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.12/v/string_type"
}

patient_08_exception_red_flag_infection
{
  "detail": "Error processing file: '>' not supported between instances of 'NoneType' and 'int'"
}

patient_10_repeat_mri_change_in_status
{
  "detail": "Error processing file: '>=' not supported between instances of 'NoneType' and 'int'"
}