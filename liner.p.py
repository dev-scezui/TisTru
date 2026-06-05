import json
with open("C:/Users/Scezui/Downloads/tistru-3af92-firebase-adminsdk-fbsvc-82df7d9704.json") as f:
    print(json.dumps(json.load(f), separators=(',', ':')))