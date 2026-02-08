import sys
import os
from streamlit.web import cli as stcli

def main():
    # Resolve absolute path to Dashboard.py
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Dashboard.py")
    
    # Construct the argument list mimicking "streamlit run Dashboard.py"
    # We add --server.headless=true to avoid random browser opening if config differs, 
    # though usually runs in default browser.
    sys.argv = [
        "streamlit",
        "run",
        script_path,
        "--global.developmentMode=false",
    ]
    
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
