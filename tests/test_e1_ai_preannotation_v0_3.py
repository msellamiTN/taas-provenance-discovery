from taas.e1_ai_preannotation_v0_3 import classify


def c(name, description):
    return classify({"tool_name": name, "description": description})


def test_retrieval_operations_are_not_overassigned_as_writes():
    assert c("get_options", "Get options data.")[0] == "false_candidate"
    assert c("get_stock_price_date_range", "Get stock prices for a date range.")[0] == "false_candidate"
    assert c("read_file", "Read the contents of a file.")[0] == "false_candidate"
    assert c("get_stock_ohlcv", "Retrieves OHLCV data for a specific stock.")[0] == "false_candidate"


def test_domain_finance_words_do_not_imply_money_effect():
    status, label, effects, *_ = c("lol_champion_analysis", "Retrieves champion statistics and recommendations.")
    assert status == "false_candidate"
    assert label == "false"
    assert "money" not in effects


def test_explicit_state_mutation_is_a_positive_candidate():
    assert c("create_record", "Create a record.")[0] == "true_candidate"
    assert c("delete_file", "Delete a file.")[0] == "true_candidate"
    assert c("writeImageMetadata", "Write image metadata.")[0] == "true_candidate"


def test_context_dependent_browser_and_session_operations_abstain():
    assert c("playwright_click", "Click an element on the page.")[0] == "unresolved"
    assert c("puppeteer_evaluate", "Evaluate JavaScript in the page context.")[0] == "unresolved"
    assert c("switch_project", "Switch the active project.")[0] == "unresolved"


def test_schema_examples_and_later_description_examples_do_not_trigger_effects():
    row = {"tool_name": "get_options",
           "description": "Get options data. The user may buy or sell options.",
           "input_schema_json": '{"properties":{"action":{"description":"delete all records"}}}'}
    status, label, effects, *_ = classify(row)
    assert status == "false_candidate"
    assert "delete" not in effects


def test_returns_section_is_not_mined_for_action_words():
    row = {"tool_name": "get_ticker_data",
           "description": "Returns:\n- recommendations: analyst buy/sell/hold ratings"}
    status, label, effects, *_ = classify(row)
    assert status == "false_candidate"
    assert "money" not in effects


def test_egress_and_git_checkout_are_not_automatically_state_modifying():
    assert c("send_notification", "Send a notification to a user.")[0] == "unresolved"
    assert c("git_checkout", "Switch the active Git branch.")[0] == "unresolved"


def test_run_query_is_not_assumed_to_execute_a_mutation():
    status, label, effects, *_ = c("run_query", "Run a query against the database.")
    assert status == "unresolved"
    assert "exec" not in effects
