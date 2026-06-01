import json
from pathlib import Path
from src.utils.errors import handle_errors,ToolError
from src.config.constants import DBFile
from src.utils.logger import get_logger


logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"



def _get_path(file_name: str) -> Path:
    return DATA_DIR / f"{file_name}.json"


@handle_errors(error_class=ToolError)
def load_db(file_name:str) -> str:
    path = _get_path(file_name)
    logger.debug(f"loading {path}")
    with open(path,"r",encoding="utf-8") as f:
        return json.load(f)
    


@handle_errors(error_class=ToolError)
def  save_db(file_name:str, data:dict) -> None:
    path = _get_path(file_name)
    logger.debug(f"saving to {path}")
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2, ensure_ascii=False)