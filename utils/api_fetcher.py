import os
import json
import re
import requests
from typing import Dict, Any

class GenericApiFetcher:
    def __init__(self, config_path: str = None):
        if config_path:
            self.config_path = config_path
        else:
            # Check updated environment variable first (set in Docker)
            env_path = os.getenv("API_CONFIG_PATH")
            if env_path and os.path.exists(env_path):
                self.config_path = env_path
            else:
                # Fallback to local source tree path relative to this script
                base_dir = os.path.dirname(os.path.abspath(__file__))
                local_path = os.path.join(base_dir, "api_mapper", "template_api_map.json")
                if os.path.exists(local_path):
                    self.config_path = local_path
                else:
                    self.config_path = "fastapi_doc_service/api_mapper/template_api_map.json"

    def _load_config(self) -> dict:
        with open(self.config_path, "r") as f:
            content = f.read()
        
        # Replace environment variables dynamically like ${BANK_API_TOKEN}
        def replacer(match):
            env_var = match.group(1)
            return os.getenv(env_var, "")
            
        resolved_content = re.sub(r'\${([A-Za-z0-9_]+)}', replacer, content)
        return json.loads(resolved_content)

    def execute_process(self, process_code: str, app_ref: str) -> Dict[str, Any]:
        config = self._load_config()
        if process_code not in config:
            raise ValueError(f"Process code '{process_code}' is not defined in the configuration map.")

        rule = config[process_code]
        method = rule.get("method", "GET").upper()
        timeout = rule.get("timeout", 10)
        
        url = rule["url"].format(app_ref=app_ref)
        headers = rule.get("headers", {})

        kwargs = {"headers": headers, "timeout": timeout}
        if method in ["POST", "PUT", "PATCH"] and "body_template" in rule:
            body_str = json.dumps(rule["body_template"])
            formatted_body = body_str.replace("{app_ref}", app_ref)
            kwargs["json"] = json.loads(formatted_body)

        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        
        return response.json()