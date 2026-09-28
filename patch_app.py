with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

imports = '''from pydantic import BaseModel
import uvicorn
from santander_runner import check_single_curp
'''
content = content.replace('from pydantic import BaseModel\nimport uvicorn', imports)

api_code = '''
class CheckCurpPayload(BaseModel):
    curp: str

@app.post("/api/check_curp")
async def check_curp_endpoint(payload: CheckCurpPayload, _: None = Depends(require_auth)):
    try:
        res = await check_single_curp(payload.curp)
        return res
    except Exception as e:
        return {"status": "ERROR", "detail": str(e)}
'''

content = content.replace('@app.get("/", response_class=HTMLResponse)', api_code + '\n@app.get("/", response_class=HTMLResponse)')

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
