from taas.e1_ai_preannotation_v0_3_1 import classify
def c(n,d): return classify({"tool_name":n,"description":d})
def test_add_protect():
 assert c("add_slide","Add a new slide.")[0:3]==("true_candidate","true","write")
 assert c("protect_document","Add password protection.")[0:3]==("true_candidate","true","write")
def test_http_methods():
 assert c("playwright_patch","Perform an HTTP PATCH request")[0:3]==("true_candidate","true","write")
 assert c("playwright_put","Perform an HTTP PUT request")[0:3]==("true_candidate","true","write")
 assert c("playwright_delete","Perform an HTTP DELETE request")[0:3]==("true_candidate","true","delete")
 assert c("playwright_get","Perform an HTTP GET request")[0:3]==("false_candidate","false","read")
def test_commit_noun_not_write():
 assert c("git_diff_staged","Shows changes that are staged for commit")[0]=="false_candidate"
def test_wait_is_not_write():
 assert c("playwright_expect_response","Ask Playwright to start waiting for a HTTP response.")[0]=="unresolved"
def test_start_process_is_exec():
 assert c("start_process","Start a new terminal process.")[0:3]==("true_candidate","true","exec")
def test_computation_not_read():
 assert c("format_table","Format a table with borders.")[0:3]==("false_candidate","false","")
def test_finance_domain_not_money():
 assert c("lol_champion_analysis","Retrieves champion statistics.")[0]=="false_candidate"
 assert c("buy_stock","Buy shares of a stock for the user's account.")[0:3]==("true_candidate","true","money")
def test_ui_abstains():
 assert c("playwright_click","Click an element on the page")[0]=="unresolved"
 assert c("switch_project","Switch the active project")[0]=="unresolved"
def test_egress_only_false():
 assert c("send_notification","Send a notification to a user.")[0:3]==("false_candidate","false","egress")
def test_schema_examples_ignored():
 row={"tool_name":"get_options","description":"Get options data. The user may buy or sell options.","input_schema_json":'{"properties":{"action":{"description":"delete all records"}}}'}
 assert classify(row)[0:3]==("false_candidate","false","read")
