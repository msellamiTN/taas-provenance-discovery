## 12306-mcp
- get-current-date: 获取当前日期，以上海时区（Asia/Shanghai, UTC+8）为准，返回格式为 "yyyy-MM-dd"。主要用于解析用户提到的相对日期（如“明天”、“下周三”），为其他需要日期的接口提供准确的日期输入。
- get-interline-tickets: 查询12306中转余票信息。尚且只支持查询前十条。
- get-station-by-telecode: 通过车站的 `station_telecode` 查询车站的详细信息，包括名称、拼音、所属城市等。此接口主要用于在已知 `telecode` 的情况下获取更完整的车站数据，或用于特殊查询及调试目的。一般用户对话流程中较少直接触发。
- get-station-code-by-names: 通过具体的中文车站名查询其 `station_code` 和车站名。此接口主要用于在用户提供**具体车站名**作为出发地或到达地时，为接口准备 `station_code` 参数。
- get-station-code-of-citys: 通过中文城市名查询代表该城市的 `station_code`。此接口主要用于在用户提供**城市名**作为出发地或到达地时，为接口准备 `station_code` 参数。
- get-stations-code-in-city: 通过中文城市名查询该城市 **所有** 火车站的名称及其对应的 `station_code`，结果是一个包含多个车站信息的列表。
- get-tickets: 查询12306余票信息。
- get-train-route-stations: 查询特定列车车次在指定区间内的途径车站、到站时间、出发时间及停留时间等详细经停信息。当用户询问某趟具体列车的经停站时使用此接口。
## Ant Design Components
- get-component-changelog: 列出 Ant Design 特定组件的更新日志
适用场景：
1. 用户询问特定组件的更新日志
2. 在知道用户 antd 版本的情况下，当用户需要实现相关组件功能时判断是否在后续版本中才实现，来决定是否需要升级依赖
- get-component-docs: 获取 Ant Design 特定组件的详细文档
适用场景：
1. 用户询问如何使用特定组件
2. 用户需要查看该组件的 api 属性
- list-component-examples: 获取 Ant Design 特定组件的代码示例
适用场景：
1. 用户询问特定组件的示例时
2. 用户想要实现某个功能时直接告知可使用的例子
3. 生成页面前需要获取组件的示例代码
- list-components: 当用户请求一个新的用户界面（UI）使用 Ant Design 组件时使用此工具。
此工具仅返回可用的组件列表。
调用此工具后，你必须编辑或添加文件，以便将代码片段集成到代码库中
## Asset_Price_MCP
- get_asset_price: Retrieves current pricing information for various assets including precious metals and cryptocurrencies
## Bazi
- buildBaziFromLunarDatetime: 根据农历时间、性别来获取八字信息。
- buildBaziFromSolarDatetime: 根据阳历时间、性别来获取八字信息。
- getBaziDetail: 根据时间（公历或农历）、性别来获取八字信息。solarDatetime和lunarDatetime必须传且只传其中一个。
- getChineseCalendar: 获取指定公历时间（默认今天）的黄历信息。
- getSolarTimes: 根据八字获取公历时间列表。返回的时间格式为：YYYY-MM-DD hh:mm:ss。例如时间1998年7月31日下午2点整表示为：1998-07-31 14:00:00
## Context7
- get-library-docs: Fetches up-to-date documentation for a library. You must call 'resolve-library-id' first to obtain the exact Context7-compatible library ID required to use this
- resolve-library-id: Resolves a package/product name to a Context7-compatible library ID and returns a list of matching libraries.

You MUST call this function before 'get-library-d
## MetaTagGenie
- writeImageMetadata: Writes metadata (tags, description, people, location) to an image file.
## airbnb
- airbnb_listing_details: Get detailed information about a specific Airbnb listing. Provide direct links to the user
- airbnb_search: Search for Airbnb listings with various filters and pagination. Provide direct links to the user
## amap-amap-sse
- maps_around_search: 周边搜，根据用户传入关键词以及坐标location，搜索出radius半径范围的POI
- maps_direction_bicycling: 骑行路径规划用于规划骑行通勤方案，规划时会考虑天桥、单行线、封路等情况。最大支持 500km 的骑行路线规划
- maps_direction_driving: 驾车路径规划 API 可以根据用户起终点经纬度坐标规划以小客车、轿车通勤出行的方案，并且返回通勤方案的数据。
- maps_direction_transit_integrated: 根据用户起终点经纬度坐标规划综合各类公共（火车、公交、地铁）交通方式的通勤方案，并且返回通勤方案的数据，跨城场景下必须传起点城市与终点城市
- maps_direction_walking: 根据输入起点终点经纬度坐标规划100km 以内的步行通勤方案，并且返回通勤方案的数据
- maps_distance: 测量两个经纬度坐标之间的距离,支持驾车、步行以及球面距离测量
- maps_geo: 将详细的结构化地址转换为经纬度坐标。支持对地标性名胜景区、建筑物名称解析为经纬度坐标
- maps_ip_location: IP 定位根据用户输入的 IP 地址，定位 IP 的所在位置
- maps_regeocode: 将一个高德经纬度坐标转换为行政区划地址信息
- maps_schema_navi: Schema唤醒客户端-导航页面，用于根据用户输入终点信息，返回一个拼装好的客户端唤醒URI，用户点击该URI即可唤起对应的客户端APP。唤起客户端后，会自动跳转到导航页面。
- maps_schema_personal_map: 用于行程规划结果在高德地图展示。将行程规划位置点按照行程顺序填入lineList，返回结果为高德地图打开的URI链接，该结果不需总结，直接返回！
- maps_schema_take_taxi: 根据用户输入的起点和终点信息，返回一个拼装好的客户端唤醒URI，直接唤起高德地图进行打车。直接展示生成的链接，不需要总结
- maps_search_detail: 查询关键词搜或者周边搜获取到的POI ID的详细信息
- maps_text_search: 关键字搜索 API 根据用户输入的关键字进行 POI 搜索，并返回相关的信息
- maps_weather: 根据城市名称或者标准adcode查询指定城市的天气
## arxiv-mcp-server
- download_paper: Download a paper and create a resource for it
- list_papers: List all existing papers available as resources
- read_paper: Read the full content of a stored paper in markdown format
- search_papers: Search for papers on arXiv with advanced filtering
## baidu-maps-sse
- map_directions: 路线规划服务: 根据起终点`位置名称`或`纬经度坐标`规划出行路线.
驾车路线规划: 根据起终点`位置名称`或`纬经度坐标`规划驾车出行路线.
骑行路线规划: 根据起终点`位置名称`或`纬经度坐标`规划骑行出行路线.
步行路线规划: 根据起终点`位置名称`或`纬经度坐标`规划步行出行路线.
公交路线规划: 根据起终点`
- map_directions_matrix: 批量算路服务: 根据起点和终点坐标计算路线规划距离和行驶时间.
批量算路目前支持驾车、骑行、步行.
步行时任意起终点之间的距离不得超过200KM, 超过此限制会返回参数错误.
驾车批量算路一次最多计算100条路线, 起终点个数之积不能超过100.
- map_geocode: 地理编码服务: 将地址解析为对应的位置坐标.地址结构越完整, 地址内容越准确, 解析的坐标精度越高.
- map_ip_location: IP定位服务: 通过所给IP获取具体位置信息和城市名称, 可用于定位IP或用户当前位置.
- map_mark: 根据旅游规划生成地图规划展示, 当根据用户的需求申城完旅游规划后, 在给用户详细讲解旅游规划的同时, 也需要使用该工具生成旅游规划地图. 该工具只会生成一个分享用的url, 并对针对该url生成一个二维码便于用户分享.
- map_place_details: 地点详情检索服务: 地点详情检索针对指定POI, 检索其相关的详情信息.
通过地点检索服务获取POI uid.使用地点详情检索功能, 传入uid, 即可检索POI详情信息, 如评分、营业时间等(不同类型POI对应不同类别详情数据).
- map_reverse_geocode: 逆地理编码服务: 根据纬经度坐标, 获取对应位置的地址描述, 所在行政区划, 道路以及相关POI等信息
- map_road_traffic: 实时路况查询服务: 查询实时交通拥堵情况, 可通过指定道路名和区域形状(矩形, 多边形, 圆形)进行实时路况查询.
道路实时路况查询: 查询具体道路的实时拥堵评价和拥堵路段、拥堵距离、拥堵趋势等信息.
矩形区域实时路况查询: 查询指定矩形地理范围的实时拥堵情况和各拥堵路段信息.
多边形区域实时路况查询: 查询指定多边形
- map_search_places: 地点检索服务: 支持检索城市内的地点信息(最小到city级别), 也可支持圆形区域内的周边地点信息检索.
城市内检索: 检索某一城市内（目前最细到城市级别）的地点信息.
周边检索: 设置圆心和半径, 检索圆形区域内的地点信息（常用于周边检索场景）.
- map_weather: 天气查询服务: 通过行政区划或是经纬度坐标查询实时天气信息及未来5天天气预报.
## basic-memory
- build_context: Build context from a memory:// URI to continue conversations naturally.
    
    Use this to follow up on previous discussions or explore related topics.
    
 
- canvas: Create an Obsidian canvas file to visualize concepts and connections.
- create_memory_project: Create a new Basic Memory project.

Creates a new project with the specified name and path. The project directory
will be created if it doesn't exist. Optionall
- delete_note: Delete a note by title or permalink
- delete_project: Delete a Basic Memory project.

Removes a project from the configuration and database. This does NOT delete
the actual files on disk - only removes the project 
- edit_note: Edit an existing markdown note using various operations like append, prepend, find_replace, or replace_section.
- get_current_project: Show the currently active project and basic stats.

Displays which project is currently active and provides basic information
about it.

Returns:
    Current pr
- list_directory: List directory contents with filtering and depth control.
- list_memory_projects: List all available projects with their status.

Shows all Basic Memory projects that are available, indicating which one
is currently active and which is the de
- move_note: Move a note to a new location, updating database and maintaining links.
- read_content: Read a file's raw content by path or permalink
- read_note: Read a markdown note by title or permalink.
- recent_activity: Get recent activity from across the knowledge base.

    Timeframe supports natural language formats like:
    - "2 days ago"  
    - "last week"
    - "yesterd
- search_notes: Search across all content in the knowledge base with advanced syntax support.
- set_default_project: Set default project in config. Requires restart to take effect.

Updates the configuration to use a different default project. This change
only takes effect aft
- switch_project: Switch to a different project context.

Changes the active project context for all subsequent tool calls.
Shows a project summary after switching successfully.

- sync_status: Check the status of file synchronization and background operations.
    
    Use this tool to:
    - Check if file sync is in progress or completed
    - Get de
- view_note: View a note as a formatted artifact for better readability.
- write_note: Create or update a markdown note. Returns a markdown formatted summary of the semantic content.
## biomcp
- alphagenome_predictor: Predict variant effects on gene regulation using Google DeepMind's AlphaGenome.

    ⚠️ PREREQUISITE: Use the 'think' tool FIRST to plan your analysis strategy!
- article_getter: Fetch detailed information for a specific article.

    Retrieves the full abstract and available text for an article by its identifier.
    Supports:
    - Pub
- article_searcher: Search PubMed/PubTator3 for research articles and preprints.

    ⚠️ PREREQUISITE: Use the 'think' tool FIRST to plan your research strategy!

    Use this tool
- fetch: Fetch comprehensive details for a specific biomedical record.

    This tool retrieves full information for articles, clinical trials, or genetic variants
    u
- search: Search biomedical literature, clinical trials, and genetic variants.

    ⚠️ IMPORTANT: Have you used the 'think' tool first? If not, STOP and use it NOW!
    T
- think: REQUIRED FIRST STEP: Perform structured sequential thinking for ANY biomedical research task.

    🚨 IMPORTANT: You MUST use this tool BEFORE any search or fetc
- trial_getter: Fetch comprehensive details for a specific clinical trial.

    Retrieves all available information for a clinical trial by its NCT ID.
    This includes protoc
- trial_locations_getter: Fetch contact and location details for a clinical trial.

    Retrieves all study locations including:
    - Facility names and addresses
    - Principal invest
- trial_outcomes_getter: Fetch outcome measures and results for a clinical trial.

    Retrieves detailed outcome information including:
    - Primary outcome measures
    - Secondary o
- trial_protocol_getter: Fetch core protocol information for a clinical trial.

    Retrieves essential protocol details including:
    - Official title and brief summary
    - Study st
- trial_references_getter: Fetch publications and references for a clinical trial.

    Retrieves all linked publications including:
    - Published results papers
    - Background litera
- trial_searcher: Search ClinicalTrials.gov for clinical studies.

    ⚠️ PREREQUISITE: Use the 'think' tool FIRST to plan your research strategy!

    Comprehensive search tool 
- variant_getter: Fetch comprehensive details for a specific genetic variant.

    Retrieves all available information for a variant including:
    - Gene location and consequenc
- variant_searcher: Search MyVariant.info for genetic variant DATABASE RECORDS.

    ⚠️ PREREQUISITE: Use the 'think' tool FIRST to plan your research strategy!

    Important: Thi
## calculator
- calculate: Calculates/evaluates the given expression.
## chess
- find_position_in_pgn: Finds the first board position in a PGN string that matches a given condition
(e.g., 'bishop on a3') and returns an image of that board.

Args:
    pgn_string: 
- get_board_visualization: Provides the current state of the chessboard as an image.
- get_turn: Indicates whose turn it is ('white' or 'black').
- get_valid_moves: Lists all legal moves for the current player in UCI notation.
- make_move: Makes a move on the board using standard algebraic notation (SAN).
Args:
    move_san: The player's move in algebraic notation (e.g., 'e4', 'Nf3', 'Bxe5').
Retu
- new_game: Starts a new game, resetting the board to the initial position.

Args:
    user_plays_white: Whether the user will play as white. Defaults to True.

Returns:
  
## coin-flip
- get-contest-details: 
- get-daily-challenge: 
- get-problem: 
- get-user-contest-ranking: 
- get-user-profile: 
- get-user-submissions: 
- search-problems: 
## datagov
- group_list: List groups on Data.gov
- package_search: Search for packages (datasets) on Data.gov
- package_show: Get details for a specific package (dataset)
- tag_list: List tags on Data.gov
## desktop-commander
- create_directory: Create a new directory or ensure a directory exists.
                        
                        Can create multiple nested directories in one operation.
 
- edit_block: Apply surgical text replacements to files.
                        
                        BEST PRACTICE: Make multiple small, focused edits rather than one la
- force_terminate: Force terminate a running terminal session.
                        
                        This command can be referenced as "DC: ..." or "use Desktop Command
- get_config: Get the complete server configuration as JSON. Config includes fields for:
                        - blockedCommands (array of blocked shell commands)
         
- get_file_info: Retrieve detailed metadata about a file or directory including:
                        - size
                        - creation time
                        -
- get_usage_stats: Get usage statistics for debugging and analysis.
                        
                        Returns summary of tool usage, success/failure rates, and perf
- give_feedback_to_desktop_commander: Open feedback form in browser to provide feedback about Desktop Commander.
                        
                        IMPORTANT: This tool simply opens th
- interact_with_process: Send input to a running process and automatically receive the response.
                        
                        CRITICAL: THIS IS THE PRIMARY TOOL FOR 
- kill_process: Terminate a running process by PID.
                        
                        Use with caution as this will forcefully terminate the specified process.
 
- list_directory: Get a detailed listing of all files and directories in a specified path.
                        
                        Use this instead of 'execute_command' 
- list_processes: List all running processes.
                        
                        Returns process information including PID, command name, CPU usage, and memory usag
- list_sessions: List all active terminal sessions.
                        
                        Shows session status including:
                        - PID: Process ident
- move_file: Move or rename files and directories.
                        
                        Can move files between directories and rename them in a single operation.
- read_file: Read the contents of a file from the file system or a URL with optional offset and length parameters.
                        
                        Prefer th
- read_multiple_files: Read the contents of multiple files simultaneously.
                        
                        Each file's content is returned with its path as a referenc
- read_process_output: Read output from a running process with intelligent completion detection.
                        
                        Automatically detects when process is
- search_code: Search for text/code patterns within file contents using ripgrep.
                        
                        Use this instead of 'execute_command' with gr
- search_files: Finds files by name using a case-insensitive substring matching.
                        
                        Use this instead of 'execute_command' with fin
- set_config_value: Set a specific configuration value by key.
                        
                        WARNING: Should be used in a separate chat from file operations and 
- start_process: Start a new terminal process with intelligent state detection.
                        
                        PRIMARY TOOL FOR FILE ANALYSIS AND DATA PROCESSI
- write_file: Write or append to file contents. 

                        CHUNKING IS STANDARD PRACTICE: Always write files in chunks of 25-30 lines maximum.
                
## docker-mcp
- create-container: Create a new standalone Docker container
- deploy-compose: Deploy a Docker Compose stack
- get-logs: Retrieve the latest logs for a specified Docker container
- list-containers: List all Docker containers
## duckduckgo-search
- duckduckgo_web_search: Performs a web search using the DuckDuckGo, ideal for general queries, news, articles, and online content. Use this for broad information gathering, recent even
## excel
- excel_copy_sheet: Copy existing sheet to a new sheet
- excel_create_table: Create a table in the Excel sheet
- excel_describe_sheets: List all sheet information of specified Excel file
- excel_read_sheet: Read values from Excel sheet with pagination.
- excel_write_to_sheet: Write values to the Excel sheet
## exchange-rate-mcp
- exchange_rate: Retrieves exchange rates using Norges Bank's API. Returns rate information including the base currency, target currency, date, and conversion rate.
## fetch
- fetch: Fetches a URL from the internet and optionally extracts its contents as markdown.

Although originally you did not have internet access, and were advised to ref
## filesystem
- create_directory: Create a new directory or ensure a directory exists. Can create multiple nested directories in one operation. If the directory already exists, this operation wi
- directory_tree: Get a recursive tree view of files and directories as a JSON structure. Each entry includes 'name', 'type' (file/directory), and 'children' for directories. Fil
- edit_file: Make line-based edits to a text file. Each edit replaces exact line sequences with new content. Returns a git-style diff showing the changes made. Only works wi
- get_file_info: Retrieve detailed metadata about a file or directory. Returns comprehensive information including size, creation time, last modified time, permissions, and type
- list_allowed_directories: Returns the list of directories that this server is allowed to access. Use this to understand which directories are available before trying to access files.
- list_directory: Get a detailed listing of all files and directories in a specified path. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixe
- list_directory_with_sizes: Get a detailed listing of all files and directories in a specified path, including sizes. Results clearly distinguish between files and directories with [FILE] 
- move_file: Move or rename files and directories. Can move files between directories and rename them in a single operation. If the destination exists, the operation will fa
- read_file: Read the complete contents of a file from the file system. Handles various text encodings and provides detailed error messages if the file cannot be read. Use t
- read_multiple_files: Read the contents of multiple files simultaneously. This is more efficient than reading files one by one when you need to analyze or compare multiple files. Eac
- search_files: Recursively search for files and directories matching a pattern. Searches through all subdirectories from the starting path. The search is case-insensitive and 
- write_file: Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Handles text 
## finance-agent-mcp-server
- get_stock_price_global_market: Get Public Available Stock Symbols from Global Marketplace

        Args:
            symbol_list (List): List of Symbols, such as Tencent: 700, Kuaishou: 1024,
## git
- git_add: Adds file contents to the staging area
- git_branch: List Git branches
- git_checkout: Switches branches
- git_commit: Records changes to the repository
- git_create_branch: Creates a new branch from an optional base branch
- git_diff: Shows differences between branches or commits
- git_diff_staged: Shows changes that are staged for commit
- git_diff_unstaged: Shows changes in the working directory that are not yet staged
- git_init: Initialize a new Git repository
- git_log: Shows the commit logs
- git_reset: Unstages all staged changes
- git_show: Shows the contents of a commit
- git_status: Shows the working tree status
## google-maps
- maps_directions: Get directions between two points
- maps_distance_matrix: Calculate travel distance and time for multiple origins and destinations
- maps_elevation: Get elevation data for locations on the earth
- maps_geocode: Convert an address into geographic coordinates
- maps_place_details: Get detailed information about a specific place
- maps_reverse_geocode: Convert coordinates into an address
- maps_search_places: Search for places using Google Places API
## google-search
- search: Perform a web search query
## hackernews
- getComment: Get a single comment by ID
- getCommentTree: Get a comment tree for a story
- getComments: Get comments for a story
- getStories: Get multiple stories by type (top, new, best, ask, show, job)
- getStory: Get a single story by ID
- getStoryWithComments: Get a story with its comments
- getUser: Get a user profile by ID
- getUserSubmissions: Get a user's submissions
- search: Search for stories and comments on Hacker News
## howtocook-mcp
- mcp_howtocook_getAllRecipes: 获取所有菜谱
- mcp_howtocook_getRecipeById: 根据菜谱名称或ID查询指定菜谱的完整详情，包括食材、步骤等
- mcp_howtocook_getRecipesByCategory: 根据分类查询菜谱，可选分类有: 水产, 早餐, 调料, 甜品, 饮品, 荤菜, 半成品加工, 汤, 主食, 素菜
- mcp_howtocook_recommendMeals: 根据用户的忌口、过敏原、人数智能推荐菜谱，创建一周的膳食计划以及大致的购物清单
- mcp_howtocook_whatToEat: 不知道吃什么？根据人数直接推荐适合的菜品组合
## hugeicons
- get_platform_usage: Get platform-specific usage instructions for Hugeicons
- list_icons: Get a list of all available Hugeicons icons
- search_icons: Search for icons by name or tags. Use commas to search for multiple icons (e.g. 'home, notification, settings')
## image-extractor
- extract_image_from_base64: Extract and analyze images from base64-encoded data. Ideal for processing screenshots from clipboard, dynamically generated images, or images embedded in applic
- extract_image_from_file: Extract and analyze images from local file paths. Supports visual content understanding, OCR text extraction, and object recognition for screenshots, photos, di
- extract_image_from_url: Extract and analyze images from web URLs. Perfect for analyzing web screenshots, online photos, diagrams, or any image accessible via HTTP/HTTPS for visual cont
## investor
- get_cnn_fear_greed_index: Max 30 days of historical data.
- get_crypto_fear_greed_index: Get historical Crypto Fear & Greed Index data.
- get_earnings_history: 
- get_financial_statements: 
- get_insider_trades: 
- get_institutional_holders: Get major institutional and mutual fund holders.
- get_options: Get options data. Dates: YYYY-MM-DD. Type: C=calls, P=puts.
- get_price_history: Get historical OHLCV data: daily intervals for ≤1y periods, monthly intervals for ≥2y periods.
- get_ticker_data: Returns:
- info: Core financial metrics (P/E ratios, margins, growth rates, debt ratios, market cap, EPS, etc.)
- calendar: Upcoming earnings dates and dividend
## kospi-kosdaq
- get_stock_fundamental: Retrieves fundamental data (PER/PBR/Dividend Yield) for a specific stock.

Args:
    fromdate (str): Start date for retrieval (YYYYMMDD)
    todate   (str): End
- get_stock_market_cap: Retrieves market capitalization data for a specific stock.

Args:
    fromdate (str): Start date for retrieval (YYYYMMDD)
    todate   (str): End date for retri
- get_stock_ohlcv: Retrieves OHLCV (Open/High/Low/Close/Volume) data for a specific stock.

Args:
    fromdate (str): Start date for retrieval (YYYYMMDD)
    todate   (str): End d
- get_stock_trading_volume: Retrieves trading volume by investor type for a specific stock.

Args:
    fromdate (str): Start date for retrieval (YYYYMMDD)
    todate   (str): End date for 
- load_all_tickers: Loads all ticker symbols and names for KOSPI and KOSDAQ into memory.

Returns:
    Dict[str, str]: A dictionary mapping tickers to stock names.
    Example: {"0
## magicuidesign_mcp
- getAnimations: Provides implementation details for blur-fade components.
- getBackgrounds: Provides implementation details for warp-background, flickering-grid, animated-grid-pattern, retro-grid, ripple, dot-pattern, grid-pattern, interactive-grid-pat
- getButtons: Provides implementation details for rainbow-button, shimmer-button, shiny-button, interactive-hover-button, animated-subscribe-button, pulsating-button, ripple-
- getComponents: Provides implementation details for marquee, terminal, hero-video-dialog, bento-grid, animated-list, dock, globe, tweet-card, client-tweet-card, orbiting-circle
- getDeviceMocks: Provides implementation details for safari, iphone-15-pro, android components.
- getSpecialEffects: Provides implementation details for animated-beam, border-beam, shine-border, magic-card, meteors, neon-gradient-card, confetti, particles, cool-mode, scratch-t
- getTextAnimations: Provides implementation details for text-animate, line-shadow-text, aurora-text, number-ticker, animated-shiny-text, animated-gradient-text, text-reveal, hyper-
- getUIComponents: Provides a comprehensive list of all Magic UI components.
## maven-deps-server
- check_maven_version_exists: Check if a specific version of a Maven dependency exists
- get_latest_release: Get the latest release version of a Maven dependency (excludes pre-releases by default)
- list_maven_versions: List Maven dependency versions sorted by last updated date (most recent first)
## mcp-crypto-price
- get-crypto-price: Get current price and 24h stats for a cryptocurrency
- get-historical-analysis: Get historical price analysis with customizable timeframe
- get-market-analysis: Get detailed market analysis including top exchanges and volume distribution
## mcp-deepwiki
- deepwiki_fetch: Fetch a deepwiki.com repo and return Markdown
## mcp-github-trending
- get_github_trending_developers: Get trending developers on github
- get_github_trending_repositories: Get trending repositories on github
## mcp-server-chart
- generate_area_chart: Generate a area chart to show data trends under continuous independent variables and observe the overall data trend, such as, displacement = velocity (average o
- generate_bar_chart: Generate a bar chart to show data for numerical comparisons among different categories, such as, comparing categorical data and for horizontal comparisons.
- generate_boxplot_chart: Generate a boxplot chart to show data for statistical summaries among different categories, such as, comparing the distribution of data points across categories
- generate_column_chart: Generate a column chart, which are best for comparing categorical data, such as, when values are close, column charts are preferable because our eyes are better
- generate_district_map: Generates regional distribution maps, which are usually used to show the administrative divisions and coverage of a dataset. It is not suitable for showing the 
- generate_dual_axes_chart: Generate a dual axes chart which is a combination chart that integrates two different chart types, typically combining a bar chart with a line chart to display 
- generate_fishbone_diagram: Generate a fishbone diagram chart to uses a fish skeleton, like structure to display the causes or effects of a core problem, with the problem as the fish head 
- generate_flow_diagram: Generate a flow diagram chart to show the steps and decision points of a process or system, such as, scenarios requiring linear process presentation.
- generate_funnel_chart: Generate a funnel chart to visualize the progressive reduction of data as it passes through stages, such as, the conversion rates of users from visiting a websi
- generate_histogram_chart: Generate a histogram chart to show the frequency of data points within a certain range. It can observe data distribution, such as, normal and skewed distributio
- generate_line_chart: Generate a line chart to show trends over time, such as, the ratio of Apple computer sales to Apple's profits changed from 2000 to 2016.
- generate_liquid_chart: Generate a liquid chart to visualize a single value as a percentage, such as, the current occupancy rate of a reservoir or the completion percentage of a projec
- generate_mind_map: Generate a mind map chart to organizes and presents information in a hierarchical structure with branches radiating from a central topic, such as, a diagram sho
- generate_network_graph: Generate a network graph chart to show relationships (edges) between entities (nodes), such as, relationships between people in social networks.
- generate_organization_chart: Generate an organization chart to visualize the hierarchical structure of an organization, such as, a diagram showing the relationship between a CEO and their d
- generate_path_map: Generate a route map to display the user's planned route, such as travel guide routes.
- generate_pie_chart: Generate a pie chart to show the proportion of parts, such as, market share and budget allocation.
- generate_pin_map: Generate a point map to display the location and distribution of point data on the map, such as the location distribution of attractions, hospitals, supermarket
- generate_radar_chart: Generate a radar chart to display multidimensional data (four dimensions or more), such as, evaluate Huawei and Apple phones in terms of five dimensions: ease o
- generate_sankey_chart: Generate a sankey chart to visualize the flow of data between different stages or categories, such as, the user journey from landing on a page to completing a p
- generate_scatter_chart: Generate a scatter chart to show the relationship between two variables, helps discover their relationship or trends, such as, the strength of correlation, data
- generate_treemap_chart: Generate a treemap chart to display hierarchical data and can intuitively show comparisons between items at the same level, such as, show disk space usage with 
- generate_venn_chart: Generate a Venn diagram to visualize the relationships between different sets, showing how they intersect and overlap, such as the commonalities and differences
- generate_violin_chart: Generate a violin chart to show data for statistical summaries among different categories, such as, comparing the distribution of data points across categories.
- generate_word_cloud_chart: Generate a word cloud chart to show word frequency or weight through text size variation, such as, analyzing common words in social media, reviews, or feedback.
## mcp-simple-arxiv
- get_paper_data: Get detailed information about a specific paper including abstract and available formats
- list_categories: List all available arXiv categories and how to use them in search
- search_papers: Search for papers on arXiv by title and abstract content.
            
You can use advanced search syntax:
- Search in title: ti:"search terms"
- Search in abst
- update_categories: Update the stored category taxonomy by fetching the latest version from arxiv.org
## memory
- add_observations: Add new observations to existing entities in the knowledge graph
- create_entities: Create multiple new entities in the knowledge graph
- create_relations: Create multiple new relations between entities in the knowledge graph. Relations should be in active voice
- delete_entities: Delete multiple entities and their associated relations from the knowledge graph
- delete_observations: Delete specific observations from entities in the knowledge graph
- delete_relations: Delete multiple relations from the knowledge graph
- open_nodes: Open specific nodes in the knowledge graph by their names
- read_graph: Read the entire knowledge graph
- search_nodes: Search for nodes in the knowledge graph based on a query
## mermaid-validator
- validateMermaid: Validates a Mermaid diagram and returns the rendered SVG if valid
## met-museum
- get-museum-object: Get a museum object by its ID, from the Metropolitan Museum of Art Collection
- list-departments: List all departments in the Metropolitan Museum of Art (Met Museum)
- search-museum-objects: Search for objects in the Metropolitan Museum of Art (Met Museum). Will return Total objects found, followed by a list of Object Ids.The parameter title should 
## mindmap
- convert_markdown_to_mindmap: Convert Markdown content to a mindmap mind map.

Args:
    markdown_content: The Markdown content to convert

Returns:
    Either the HTML content or the file p
## music-analysis
- beat_track: Computes the beat track of the given audio time series using librosa.
The beat track is a representation of the audio signal in terms of its
rhythmic content, w
- chroma_cqt: Computes the chroma CQT of the given audio time series using librosa.
The chroma CQT is a representation of the audio signal in terms of its
chromatic content, 
- download_from_url: Downloads a file from a given URL and returns the path to the downloaded file.
Be careful, you will never know the name of the song.
- download_from_youtube: Downloads a file from a given youtube URL and returns the path to the downloaded file.
Be careful, you will never know the name of the song.
- get_duration: Returns the total duration (in seconds) of the given audio time series.
- load: Loads an audio file and returns the path to the audio time series
Offset and duration are optional, in seconds.
Be careful, you will never know the name of the 
- mfcc: Computes the MFCC of the given audio time series using librosa.
The MFCC is a representation of the audio signal in terms of its
spectral content, which is usef
- tempo: Estimates the tempo (in BPM) of the given audio time series using librosa.
Offset and duration are optional, in seconds.
## npm-sentinel-mcp
- npmAlternatives: Find alternative packages with similar functionality
- npmChangelogAnalysis: Analyze changelog and release history of packages
- npmCompare: Compare multiple NPM packages based on various metrics
- npmDeprecated: Check if packages are deprecated
- npmDeps: Analyze dependencies and devDependencies of an NPM package
- npmLatest: Get the latest version and changelog of an NPM package
- npmLicenseCompatibility: Check license compatibility between multiple packages
- npmMaintainers: Get maintainers information for NPM packages
- npmMaintenance: Analyze package maintenance metrics
- npmPackageReadme: Get the README content for NPM packages
- npmQuality: Analyze package quality metrics
- npmRepoStats: Get repository statistics for NPM packages
- npmScore: Get consolidated package score based on quality, maintenance, and popularity metrics
- npmSearch: Search for NPM packages with optional limit
- npmSize: Get package size information including dependencies and bundle size
- npmTrends: Get download trends and popularity metrics for packages
- npmTypes: Check TypeScript types availability and version for a package
- npmVersions: Get all available versions of an NPM package
- npmVulnerabilities: Check for known vulnerabilities in packages
## npx_fetch
- fetch_html: Fetch a website and return the content as HTML
- fetch_json: Fetch a JSON file from a URL
- fetch_markdown: Fetch a website and return the content as Markdown
- fetch_txt: Fetch a website, return the content as plain text (no HTML)
## okppt
- add_slide_with_layout: Inserts a new slide with a specified layout into a presentation and returns a JSON string of the result.
- analyze_presentation_layouts: Analyzes the layout details of a PowerPoint presentation and returns a JSON string of the analysis.
- clear_placeholders_from_slides: Clears content from placeholders in specified slides of a presentation and returns a JSON string of the result.
- convert_svg_to_png: 将SVG文件转换为PNG图像。

Args:
    svg_path: SVG文件路径
    output_path: 输出PNG文件路径，如果未指定则使用相同文件名但扩展名为.png
    
Returns:
    操作结果消息
- copy_svg_slide: 专门用于复制包含SVG图像的幻灯片，确保SVG和相关引用都被正确复制。

此函数使用直接操作PPTX内部XML文件的方式，确保SVG图像及其引用在复制过程中完全保留。
与普通的copy_slide函数相比，此函数特别关注SVG图像的复制，保证SVG的矢量属性在复制后依然可用。

Args:
    source_ppt
- delete_slide: 从PPTX文件中删除指定编号的幻灯片。

!!!注意：

在使用SVG替换PPT幻灯片内容时，我们发现了一些关键点，以下是正确替换PPT内容的方法总结：

### 正确替换PPT内容的方法

1. **完全替换法**（最可靠）：
- 删除需要替换的幻灯片（使用`delete_slide`功能）
- 在同一位置插入空白幻
- get_file_info: 获取文件信息，如存在状态、大小等。

Args:
    file_path: 要查询的文件路径
    
Returns:
    文件信息
- get_pptx_info: 获取PPTX文件的基本信息，包括幻灯片数量。

Args:
    pptx_path: PPTX文件路径
    
Returns:
    包含文件信息和幻灯片数量的字符串
- insert_blank_slide: 在PPTX文件的指定位置插入一个空白幻灯片。

!!!注意：

在使用SVG替换PPT幻灯片内容时，我们发现了一些关键点，以下是正确替换PPT内容的方法总结：

### 正确替换PPT内容的方法

1. **完全替换法**（最可靠）：
- 删除需要替换的幻灯片（使用`delete_slide`功能）
- 在同一位置插入
- insert_svg: 将SVG图像插入到PPTX文件的指定位置。(如果需要替换已有的幻灯片，请组合使用`delete_slide`和`insert_blank_slide`功能)
如果未提供PPTX路径，将自动创建一个临时文件，位于服务器同级目录的tmp目录。
如果未提供输出路径，将使用标准输出目录，位于服务器同级目录的output目录。

- list_files: 列出目录中的文件，可选按文件类型过滤。
如需查看svg文件是否正确保存，请输入svg文件的保存路径。
Args:
    directory: 要列出文件的目录路径
    file_type: 文件类型过滤，可以是 "svg" 或 "pptx"
    
Returns:
    文件列表（每行一个文件）
- save_svg_code: 将SVG代码保存为SVG文件并返回保存的绝对路径。
!!!注意：特殊字符如"&"需要转义为"&amp;"
Args:
    svg_code: SVG代码内容
    
Returns:
    操作结果消息，包含保存的文件路径或错误信息
- set_placeholder_value: Assigns content to a specific placeholder on a specific slide and returns a JSON string of the result.
- svg_prompt: 使用SVG设计宗师角色提示，当用户希望大模型生成或优化ppt时，使用此prompt对用户需求进行细化
## opgg-mcp
- esports-lol-schedules: Get upcoming LoL match schedules.
- esports-lol-team-standings: Get team standings for a LoL league.
- lol-brawl-champion-tier-rank: Retrieves champion tier ranking list in brawl mode.
- lol-champion-analysis: Retrieves very detailed information about a specific champion, such as win rate, pick rate, recommended builds, recommended skill order, recommended items, etc.
- lol-champion-leader-board: Retrieves the leaderboard of master players who play a specific champion well. You can also look up the high ranked players, like the high winrate 5 players in 
- lol-champion-meta-data: Retrieves meta data for a specific champion, including statistics and performance metrics.
- lol-champion-positions-data: Retrieves the analytics of champions by each positions. You can also look up the winrate, banrate, plays, wins, kills, kda and etc. `tier_data` is champion tier
- lol-champion-skin-sale: Retrieves information about champion skins that are currently on sale.
- lol-summoner-game-history: Retrieves the recent match history of a specific summoner. If a user mentions a specific summoner, wants to know about their recent matches, wants to know how t
- lol-summoner-renewal: Renew the summoner's data of OP.GG through RiotAPI. When you retrieve summoner data, you *must* always call this function first, and then call the next function
- lol-summoner-search: Retrieves information about a specific summoner, such as their rank, win rate, and recent match history. If a user mentions a specific summoner or wants to know
- tft-champion-item-build: TFT tool for retrieving champion item build information.
- tft-meta-item-combinations: TFT tool for retrieving information about item combinations and recipes.
- tft-meta-trend-deck-list: TFT deck list tool for retrieving current meta decks.
- tft-play-style-comment: This tool provides comments on the playstyle of TFT champions.
- tft-recommend-champion-for-item: TFT tool for retrieving champion recommendations for a specific item.
- valorant-agents-composition-with-map: Retrieve agent composition data for a Valorant map.
- valorant-characters-statistics: Retrieve character statistics data for Valorant, optionally filtered by map.
- valorant-leaderboard: Fetch Valorant leaderboard by region
- valorant-meta-characters: Valorant character meta data
- valorant-meta-maps: Valorant map meta data
- valorant-player-match-history: Retrieve match history for a Valorant player using their game name and tag line.
## osm-mcp-server
- analyze_commute: Perform a detailed commute analysis between home and work locations.

This advanced tool analyzes commute options between two locations (typically home and work
- analyze_neighborhood: Generate a comprehensive neighborhood analysis focused on livability factors.

This advanced analysis tool evaluates a neighborhood based on multiple livability
- explore_area: Generate a comprehensive profile of an area including all amenities and features.

This powerful analysis tool creates a detailed overview of a neighborhood or 
- find_ev_charging_stations: Locate electric vehicle charging stations near a specific location.

This specialized search tool identifies EV charging infrastructure within a specified
dista
- find_nearby_places: Discover points of interest and amenities near a specific location.

This tool performs a comprehensive search around a geographic point to identify
nearby esta
- find_parking_facilities: Locate parking facilities near a specific location.

This tool finds parking options (lots, garages, street parking) near a specified location.
Results can be f
- find_schools_nearby: Locate educational institutions near a specific location, filtered by education level.

This specialized search tool identifies schools, colleges, and other edu
- geocode_address: Convert an address or place name to geographic coordinates with detailed location information.

This tool takes a text description of a location (such as an add
- get_route_directions: Calculate detailed route directions between two geographic points.

This tool provides comprehensive turn-by-turn navigation directions between any two location
- reverse_geocode: Convert geographic coordinates to a detailed address and location description.

This tool takes a specific point on Earth (latitude and longitude) and returns 

- search_category: Search for specific types of places within a defined geographic area.

This tool allows targeted searches for places matching specific categories within
a recta
- suggest_meeting_point: Find the optimal meeting place for multiple people coming from different locations.

This tool calculates a central meeting point based on the locations of mult
## painter
- drawing_fillRectangle: Fill a rectangle on the drawing canvas with a specified color and coordinates.
- drawing_generateCanvas: Generate a new drawing canvas with specified width and height.
- drawing_getCanvasData: Get the current pixel data of the drawing canvas as JSON.
- drawing_getCanvasPng: Get the current drawing canvas as a PNG image (base64 encoded).
## paypal
- create_invoice: Create Invoices on PayPal.

This function is used to create an invoice in the PayPal system. It allows you to generate a new invoice, specifying details such as
- create_order: Create an order in PayPal.

This tool is used to create a new order in PayPal. This is typically the first step in initiating a payment flow. It sets up an orde
- create_product: Create a product in PayPal using product catalog - create products API.
This function creates a new product that will be used in subscription plans, subscriptio
- create_refund: Initiate a refund for a PayPal payment capture.
If you have an order ID instead of a capture ID, first use the get order tool to obtain the capture ID from the 
- create_shipment_tracking: Create a shipment for a transaction in PayPal.
This function creates a shipment record for a specific transaction, allowing you to track the shipment status and
- create_subscription_plan: Create a subsctiption plan in PayPal using subscription - create plan API.
This function creates a new subscription plan that defines pricing and billing cycle 
## pdf-reader-mcp
- read_pdf: Reads content/metadata from one or more PDFs (local/URL). Each source can specify pages to extract.
## playwright
- clear_codegen_session: Clear a code generation session without generating a test
- end_codegen_session: End a code generation session and generate the test file
- get_codegen_session: Get information about a code generation session
- playwright_assert_response: Wait for and validate a previously initiated HTTP response wait operation.
- playwright_click: Click an element on the page
- playwright_click_and_switch_tab: Click a link and switch to the newly opened tab
- playwright_close: Close the browser and release all resources
- playwright_console_logs: Retrieve console logs from the browser with filtering options
- playwright_custom_user_agent: Set a custom User Agent for the browser
- playwright_delete: Perform an HTTP DELETE request
- playwright_drag: Drag an element to a target location
- playwright_evaluate: Execute JavaScript in the browser console
- playwright_expect_response: Ask Playwright to start waiting for a HTTP response. This tool initiates the wait operation but does not wait for its completion.
- playwright_fill: fill out an input field
- playwright_get: Perform an HTTP GET request
- playwright_get_visible_html: Get the HTML content of the current page. By default, all <script> tags are removed from the output unless removeScripts is explicitly set to false.
- playwright_get_visible_text: Get the visible text content of the current page
- playwright_go_back: Navigate back in browser history
- playwright_go_forward: Navigate forward in browser history
- playwright_hover: Hover an element on the page
- playwright_iframe_click: Click an element in an iframe on the page
- playwright_iframe_fill: Fill an element in an iframe on the page
- playwright_navigate: Navigate to a URL
- playwright_patch: Perform an HTTP PATCH request
- playwright_post: Perform an HTTP POST request
- playwright_press_key: Press a keyboard key
- playwright_put: Perform an HTTP PUT request
- playwright_save_as_pdf: Save the current page as a PDF file
- playwright_screenshot: Take a screenshot of the current page or a specific element
- playwright_select: Select an element on the page with Select tag
- playwright_upload_file: Upload a file to an input[type='file'] element on the page
- start_codegen_session: Start a new code generation session to record Playwright actions
## ppt
- add_bullet_points: Add bullet points to a placeholder.
- add_chart: Add a chart to a slide with comprehensive formatting options.
- add_connector: Add connector lines/arrows between points on a slide.

Args:
    slide_index: Index of the slide (0-based)
    connector_type: Type of connector ("straight", "e
- add_shape: Add an auto shape to a slide with enhanced options.
- add_slide: Add a new slide to the presentation with optional background styling.
- add_table: Add a table to a slide with enhanced formatting options.
- apply_picture_effects: Apply multiple picture effects in combination.
- apply_professional_design: Unified professional design tool for themes, slides, and visual enhancements.
This applies professional styling and themes rather than structural layout changes
- apply_slide_template: Apply a structured layout template to an existing slide.
This modifies slide layout and content structure using predefined templates.

Args:
    slide_index: In
- auto_generate_presentation: Automatically generate a presentation based on topic and preferences.

Args:
    topic: Main topic/theme for the presentation
    slide_count: Number of slides 
- create_presentation: Create a new PowerPoint presentation.
- create_presentation_from_template: Create a new PowerPoint presentation from a template file.
- create_presentation_from_templates: Create a complete presentation from a sequence of templates.

Args:
    template_sequence: List of template configurations, each containing:
        - template_
- create_slide_from_template: Create a new slide using a layout template.

Args:
    template_id: ID of the template to use (e.g., 'title_slide', 'text_with_image')
    color_scheme: Color s
- format_table_cell: Format a specific table cell.
- get_presentation_info: Get information about a presentation.
- get_server_info: Get information about the MCP server.
- get_slide_info: Get information about a specific slide.
- get_template_file_info: Get information about a template file including layouts and properties.
- get_template_info: Get detailed information about a specific template.

Args:
    template_id: ID of the template to get information about
- list_presentations: List all loaded presentations.
- list_slide_templates: List all available slide layout templates.
- manage_fonts: Unified font management tool for analysis, optimization, and recommendations.
- manage_hyperlinks: Manage hyperlinks in text shapes and runs.

Args:
    operation: Operation type ("add", "remove", "list", "update")
    slide_index: Index of the slide (0-based
- manage_image: Unified image management tool for adding and enhancing images.
- manage_slide_masters: Access and manage slide master properties and layouts.

Args:
    operation: Operation type ("list", "get_layouts", "get_info")
    master_index: Index of the s
- manage_slide_transitions: Manage slide transitions and timing.

Args:
    slide_index: Index of the slide (0-based)
    operation: Operation type ("set", "remove", "get")
    transition_
- manage_text: Unified text management tool for adding, formatting, validating text, and formatting multiple text runs.
- open_presentation: Open an existing PowerPoint presentation from a file.
- optimize_slide_text: Optimize text elements on a slide for better readability and fit.

Args:
    slide_index: Index of the slide to optimize
    auto_resize: Whether to automatical
- populate_placeholder: Populate a placeholder with text.
- save_presentation: Save a presentation to a file.
- set_core_properties: Set core document properties.
- switch_presentation: Switch to a different loaded presentation.
- update_chart_data: Replace existing chart data with new categories and series.

Args:
    slide_index: Index of the slide (0-based)
    shape_index: Index of the chart shape (0-ba
## puppeteer
- puppeteer_click: Click an element on the page
- puppeteer_evaluate: Execute JavaScript in the browser console
- puppeteer_fill: Fill out an input field
- puppeteer_hover: Hover an element on the page
- puppeteer_navigate: Navigate to a URL
- puppeteer_screenshot: Take a screenshot of the current page or a specific element
- puppeteer_select: Select an element on the page with Select tag
## random-number
- random_choices: Choose k items from population with replacement, optionally weighted.

Args:
    population: List of items to choose from
    k: Number of items to choose (defa
- random_float: Generate a random float between low and high.

Args:
    low: Lower bound (default 0.0)
    high: Upper bound (default 1.0)

Returns:
    Random float between l
- random_int: Generate a random integer between low and high (inclusive).

Args:
    low: Lower bound (inclusive)
    high: Upper bound (inclusive)

Returns:
    Random integ
- random_sample: Choose k unique items from population without replacement.

Args:
    population: List of items to choose from
    k: Number of items to choose

Returns:
    Li
- random_shuffle: Return a new list with items in random order.

Args:
    items: List of items to shuffle

Returns:
    New list with items in random order
- secure_random_int: Generate a secure random integer below upper_bound.

Args:
    upper_bound: Upper bound (exclusive)

Returns:
    Random integer in range [0, upper_bound)
- secure_token_hex: Generate a secure random hex token.

Args:
    nbytes: Number of random bytes to generate (default 32)

Returns:
    Hex string containing 2*nbytes characters
## searxng
- document_reader: Read content from non-image document-files at specified paths, supporting various file formats: .pdf, .docx, .txt, .html, .csv
- docx_to_html: Convert DOCX to HTML while preserving formatting
- docx_to_pdf: Convert DOCX files to PDF format
- excel_read: Read Excel file and convert to JSON format while preserving structure
- format_convert: Convert between different document formats (Markdown, HTML, XML, JSON)
- html_cleaner: Clean HTML by removing unnecessary tags and attributes
- html_extract_resources: Extract all resources (images, videos, links) from HTML
- html_formatter: Format and beautify HTML code
- html_to_markdown: Convert HTML to Markdown format
- html_to_text: Convert HTML to plain text while preserving structure
- pdf_merger: Merge multiple PDF files into one
- pdf_splitter: Split a PDF file into multiple files
- text_diff: Compare two text files and show differences
- text_encoding_converter: Convert text between different encodings
- text_formatter: Format text with proper indentation and line spacing
- text_splitter: Split text file by specified delimiter or line count
## sequential-thinking
- sequentialthinking: A detailed tool for dynamic and reflective problem-solving through thoughts.
This tool helps analyze problems through a flexible thinking process that can adapt
## shadcn-ui-server
- get_component_details: Get detailed information about a specific shadcn/ui component
- get_component_examples: Get usage examples for a specific shadcn/ui component
- list_shadcn_components: Get a list of all available shadcn/ui components
- search_components: Search for shadcn/ui components by keyword
## sitemap
- get_sitemap_pages: Get all pages from a website's sitemap with optional limits and filtering options. Supports cursor-based pagination.
- get_sitemap_stats: Get comprehensive statistics about a website's sitemap structure
- get_sitemap_tree: Fetch and parse the sitemap tree from a website URL
- parse_sitemap_content: Parse a sitemap directly from its XML or text content
## taskmanager
- add_tasks_to_request: Add new tasks to an existing request. This allows extending a request with additional tasks.

A progress table will be displayed showing all tasks including the
- approve_request_completion: After all tasks are done and approved, this tool finalizes the entire request. The user must call this to confirm that the request is fully completed.

A progre
- approve_task_completion: Once the assistant has marked a task as done using 'mark_task_done', the user must call this tool to approve that the task is genuinely completed. Only after th
- delete_task: Delete a specific task from a request. Only uncompleted tasks can be deleted.

A progress table will be displayed showing the remaining tasks after deletion.
- get_next_task: Given a 'requestId', return the next pending task (not done yet). If all tasks are completed, it will indicate that no more tasks are left and that you must wai
- list_requests: List all requests with their basic information and summary of tasks. This provides a quick overview of all requests in the system.
- mark_task_done: Mark a given task as done after you've completed it. Provide 'requestId' and 'taskId', and optionally 'completedDetails'.

After marking a task as done, a progr
- open_task_details: Get details of a specific task by 'taskId'. This is for inspecting task information at any point.
- request_planning: Register a new user request and plan its associated tasks. You must provide 'originalRequest' and 'tasks', and optionally 'splitDetails'.

This tool initiates a
- update_task: Update an existing task's title and/or description. Only uncompleted tasks can be updated.

A progress table will be displayed showing the updated task informat
## tavily-mcp
- tavily-crawl: A powerful web crawler that initiates a structured web crawl starting from a specified base URL. The crawler expands from that point like a tree, following inte
- tavily-extract: A powerful web content extraction tool that retrieves and processes raw content from specified URLs, ideal for data collection, content analysis, and research t
- tavily-map: A powerful web mapping tool that creates a structured map of website URLs, allowing you to discover and analyze site structure, content organization, and naviga
- tavily-search: A powerful web search tool that provides comprehensive, real-time results using Tavily's AI search engine. Returns relevant web content with customizable parame
## text-editor
- edit_text_file_contents: A line editor that supports editing text file contents by specifying line ranges and content. It handles multiple patches in a single operation with hash-based 
- get_text_file_contents: Read text file contents from multiple files and line ranges. Returns file contents with hashes for concurrency control and line numbers for reference. The hashe
## time
- convert_time: Convert time between timezones
- get_current_time: Get current time in a specific timezones
## trends-hub
- get-36kr-trending: 获取 36 氪热榜，提供创业、商业、科技领域的热门资讯，包含投融资动态、新兴产业分析和商业模式创新信息
- get-9to5mac-news: 获取 9to5Mac 苹果相关新闻，包含苹果产品发布、iOS 更新、Mac 硬件、应用推荐及苹果公司动态的英文资讯
- get-bbc-news: 获取 BBC 新闻，提供全球新闻、英国新闻、商业、政治、健康、教育、科技、娱乐等资讯
- get-bilibili-rank: 获取哔哩哔哩视频排行榜，包含全站、动画、音乐、游戏等多个分区的热门视频，反映当下年轻人的内容消费趋势
- get-douban-rank: 获取豆瓣实时热门榜单，提供当前热门的图书、电影、电视剧、综艺等作品信息，包含评分和热度数据
- get-douyin-trending: 获取抖音热搜榜单，展示当下最热门的社会话题、娱乐事件、网络热点和流行趋势
- get-gcores-new: 获取机核网游戏相关资讯，包含电子游戏评测、玩家文化、游戏开发和游戏周边产品的深度内容
- get-ifanr-news: 获取爱范儿科技快讯，包含最新的科技产品、数码设备、互联网动态等前沿科技资讯
- get-infoq-news: 获取 InfoQ 技术资讯，包含软件开发、架构设计、云计算、AI等企业级技术内容和前沿开发者动态
- get-juejin-article-rank: 获取掘金文章榜，包含前端开发、后端技术、人工智能、移动开发及技术架构等领域的高质量中文技术文章和教程
- get-netease-news-trending: 获取网易新闻热点榜，包含时政要闻、社会事件、财经资讯、科技动态及娱乐体育的全方位中文新闻资讯
- get-nytimes-news: 获取纽约时报新闻，包含国际政治、经济金融、社会文化、科学技术及艺术评论的高质量英文或中文国际新闻资讯
- get-smzdm-rank: 获取什么值得买热门，包含商品推荐、优惠信息、购物攻略、产品评测及消费经验分享的实用中文消费类资讯
- get-sspai-rank: 获取少数派热榜，包含数码产品评测、软件应用推荐、生活方式指南及效率工作技巧的优质中文科技生活类内容
- get-tencent-news-trending: 获取腾讯新闻热点榜，包含国内外时事、社会热点、财经资讯、娱乐动态及体育赛事的综合性中文新闻资讯
- get-thepaper-trending: 获取澎湃新闻热榜，包含时政要闻、财经动态、社会事件、文化教育及深度报道的高质量中文新闻资讯
- get-theverge-news: 获取 The Verge 新闻，包含科技创新、数码产品评测、互联网趋势及科技公司动态的英文科技资讯
- get-toutiao-trending: 获取今日头条热榜，包含时政要闻、社会事件、国际新闻、科技发展及娱乐八卦等多领域的热门中文资讯
- get-weibo-trending: 获取微博热搜榜，包含时事热点、社会现象、娱乐新闻、明星动态及网络热议话题的实时热门中文资讯
- get-weread-rank: 获取微信读书排行榜，包含热门小说、畅销书籍、新书推荐及各类文学作品的阅读数据和排名信息
- get-zhihu-trending: 获取知乎热榜，包含时事热点、社会话题、科技动态、娱乐八卦等多领域的热门问答和讨论的中文资讯
## weather
- get_weather: Get current weather and forecast for a specific location.

Args:
    latitude: Latitude of the location
    longitude: Longitude of the location
    location_na
- get_weather_by_city: Get weather for a city by name using geocoding.

Args:
    city: Name of the city
    country_code: Optional 2-letter country code (e.g., "US", "GB")
    temper
## web3-research-mcp
- create-research-plan: 
- fetch-content: 
- list-resources: 
- research-source: 
- research-token: 
- research-with-keywords: 
- search: 
- search-source: 
- update-status: 
## whois
- whois_as: Looksup whois information about the Autonomous System Number (ASN)
- whois_domain: Looksup whois information about the domain
- whois_ip: Looksup whois information about the IP
- whois_tld: Looksup whois information about the Top Level Domain (TLD)
## wikipedia
- extract_key_facts: Extract key facts from a Wikipedia article, optionally focused on a topic.
- get_article: Get the full content of a Wikipedia article.
- get_links: Get the links contained within a Wikipedia article.
- get_related_topics: Get topics related to a Wikipedia article based on links and categories.
- get_sections: Get the sections of a Wikipedia article.
- get_summary: Get a summary of a Wikipedia article.
- search_wikipedia: Search Wikipedia for articles matching a query.
- summarize_article_for_query: Get a summary of a Wikipedia article tailored to a specific query.
- summarize_article_section: Get a summary of a specific section of a Wikipedia article.
## word-document-server
- add_endnote_to_document: Add an endnote to a specific paragraph in a Word document.
- add_footnote_to_document: Add a footnote to a specific paragraph in a Word document.
- add_heading: Add a heading to a Word document.
- add_page_break: Add a page break to the document.
- add_paragraph: Add a paragraph to a Word document.
- add_picture: Add an image to a Word document.
- add_table: Add a table to a Word document.
- convert_to_pdf: Convert a Word document to PDF format.
- copy_document: Create a copy of a Word document.
- create_custom_style: Create a custom style in the document.
- create_document: Create a new Word document with optional metadata.
- customize_footnote_style: Customize footnote numbering and formatting in a Word document.
- delete_paragraph: Delete a paragraph from a document.
- find_text_in_document: Find occurrences of specific text in a Word document.
- format_table: Format a table with borders, shading, and structure.
- format_text: Format a specific range of text within a paragraph.
- get_document_info: Get information about a Word document.
- get_document_outline: Get the structure of a Word document.
- get_document_text: Extract all text from a Word document.
- get_paragraph_text_from_document: Get text from a specific paragraph in a Word document.
- list_available_documents: List all .docx files in the specified directory.
- protect_document: Add password protection to a Word document.
- search_and_replace: Search for text and replace all occurrences.
- unprotect_document: Remove password protection from a Word document.
## wuwa-mcp
- get_artifact_info: 获取库街区上的声骸详细信息并以 Markdown 格式返回。

Args:
    artifact_name: 要查询的声骸套装的中文名称。

Returns:
    包含声骸信息的 Markdown 字符串，
    或者在找不到声骸或获取数据失败时返回错误消息。
- get_character_info: 获取库街区上的角色详细信息包括角色技能，养成攻略等，并以 Markdown 格式返回。

Args:
    character_name: 要查询的角色的中文名称。

Returns:
    包含角色信息的 Markdown 字符串，
    或者在找不到角色或获取数据失败时返回错误消息。
- get_character_profile: 获取库街区上的角色档案信息并以 Markdown 格式返回。

Args:
    character_name: 要查询的角色的中文名称。

Returns:
    包含角色档案信息的 Markdown 字符串，
    或者在找不到角色或获取数据失败时返回错误消息。
## yahoo-finance
- get_cashflow: Get cashflow for a given stock symbol.
- get_current_stock_price: Get the current stock price based on stock symbol.
- get_dividends: Get dividends for a given stock symbol.
- get_earning_dates: Get earning dates.
- get_historical_stock_prices: Get historical stock prices for a given stock symbol.
- get_income_statement: Get income statement for a given stock symbol.
- get_news: Get news for a given stock symbol.
- get_recommendations: Get analyst recommendations for a given symbol.
- get_stock_price_by_date: Get the stock price for a given stock symbol on a specific date.
- get_stock_price_date_range: Get the stock prices for a given date range for a given stock symbol.
## yfmcp
- get_price_history: Fetch historical price data for a given stock symbol over a specified period and interval.
- get_ticker_info: Retrieve stock data including company info, financials, trading metrics and governance data.
- get_ticker_news: Fetches recent news articles related to a specific stock symbol with title, content, and source details.
- get_top: Get top entities (ETFs, mutual funds, companies, growth companies, or performing companies) in a sector.
- search: Fetches and organizes search results from Yahoo Finance, including stock quotes and news articles.
## ygocdb
- get_card_by_id: 通过卡牌ID获取单张游戏王卡牌的详细信息
- get_card_image: 通过卡牌ID获取游戏王卡牌的图片
- search_cards: 通过关键字搜索游戏王卡牌，可以搜索卡牌名称、效果文本等。
## youtube-transcript
- get_transcript: Extract transcript from a YouTube video URL or ID
