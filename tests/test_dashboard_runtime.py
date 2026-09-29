from scripts.dashboard import summarize


def test_retrieval_success_includes_successful_responses_and_failures():
    rows = [
        {'event':'request_received','ts':'2026-09-29T09:00:00Z'},
        {'event':'request_received','ts':'2026-09-29T09:00:01Z'},
        {'event':'response_sent','ts':'2026-09-29T09:00:02Z','latency_ms':500,'ttft_ms':50,'tool_success':True,'quality_score':0.8},
        {'event':'request_failed','tool_success':False,'error_type':'RuntimeError'},
    ]
    result=summarize(rows)
    assert result['errors']=={'error rate':50.0,'retrieval success':50.0}
    assert result['latency']['P95']==500
    assert result['error_breakdown']=={'RuntimeError':1}


def test_no_traffic_is_not_reported_as_zero_error_rate():
    assert summarize([])['errors']=={'error rate':None,'retrieval success':None}
