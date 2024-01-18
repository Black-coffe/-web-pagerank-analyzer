<h1>Web PageRank Analyzer</h1>
    <p>Web PageRank Analyzer is a Python-based tool designed to analyze web pages and calculate the PageRank for internal links. It is an ideal solution for SEO professionals, webmasters, and digital marketers looking to understand the link structure and importance of various pages on a website.</p>
    <p>The script works by crawling a website, starting from a specified URL, and evaluates the significance of pages based on the PageRank algorithm.</p>
    <div>
    <h2>Features</h2>
      <ul>
        <li><strong>Web Crawling</strong>: Recursively navigates through a website from a given start URL, collecting data on each encountered page.</li>
        <li><strong>PageRank Calculation</strong>: Implements the PageRank algorithm to evaluate the relative importance of pages within the site.</li>
        <li><strong>HTML Parsing</strong>: Uses BeautifulSoup to parse HTML content, enabling precise extraction of links and page content.</li>
        <li><strong>Link Filtering</strong>: Provides functionality to exclude specific links, tags, and classes from the analysis, such as navigation menus, footers, and sidebars.</li>
        <li><strong>Data Storage</strong>: Saves crawled data in a SQLite database for efficient processing and retrieval.</li>
        <li><strong>Excel Export</strong>: Compiles and exports the analysis results into an Excel file for easy review and reporting.</li>
        <li><strong>Customizable Settings</strong>: Offers a separate configuration file (config.py) for easy adjustments of crawling parameters, excluded elements, and other settings.</li>
    </ul>
      <h2>Configuration</h2>
    <p>The script utilizes a config.py file for easy customization:</p>
    <ul>
        <li><strong>LOGGING_LEVEL</strong>: Defines the logging level for the script's output.</li>
        <li><strong>TIMEOUT</strong>: Specifies the timeout for HTTP requests during web crawling.</li>
        <li><strong>DAMPING_FACTOR</strong>: Sets the damping factor for the PageRank calculation.</li>
        <li><strong>OUTPUT_DIR</strong>: Determines the directory for saving output files.</li>
        <li><strong>START_URL</strong>: The initial URL from which the web crawling starts.</li>
        <li><strong>DB_FILE</strong>: The name of the SQLite database file for storing crawled data.</li>
        <li><strong>EXCLUDED_CLASSES, EXCLUDED_IDS, EXCLUDED_TAGS</strong>: Lists of HTML classes, IDs, and tags to exclude from link analysis.</li>
        <li><strong>EXCLUDED_LINKS_BEFORE_H1</strong>: Boolean flag to exclude links appearing before the first h1 tag on each page.</li>
        <li><strong>STOP_LINK_LINKS</strong>: A list of specific links to be excluded from the PageRank calculation.</li>
    </ul>
      <h2>Usage</h2>
    <p>To run the Web PageRank Analyzer, follow these steps:</p>
    <ol>
        <li>Ensure you have Python installed on your system.</li>
        <li>Install required Python packages: requests, bs4 (BeautifulSoup), networkx, pandas, and sqlite3.</li>
        <li>Configure the config.py file according to your requirements.</li>
        <li>Run the script using the command: python main.py.</li>
    </ol>
      <h2>Output</h2>
    <p>The script provides the following outputs:</p>
    <ul>
        <li>A SQLite database file containing crawled data.</li>
        <li>An Excel file with detailed analytics, including PageRank scores, link counts, and error pages.</li>
    </ul>
      <h2>License</h2>
    <p>This project is open-source and available under the MIT License.</p>
      <h2>Contributing</h2>
    <p>Contributions to the Web PageRank Analyzer are welcome. Please ensure to follow the project's coding standards and submit a pull request for review.</p>
</div>
