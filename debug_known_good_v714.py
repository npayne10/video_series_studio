import json
import time
import urllib.error
import urllib.request
from pathlib import Path

COMFY_URL = "http://127.0.0.1:8188"

WORKFLOW = Path(
    r"D:\VSCS\video_series_studio\resources\workflows\workflows\video_production_engine_v7_1_4_api.json"
)

PRODUCTION_PACKAGE = Path(
    r"D:\Xorix\Xorix_Studio_v4.0.3.4\production\Trailer\compiled\preview\ACPP-T01-A01-C001\production_package.json"
)

LOADER_NODE = "107"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    print("Workflow:", WORKFLOW)
    print("Production package:", PRODUCTION_PACKAGE)

    if not WORKFLOW.exists():
        raise FileNotFoundError(f"Workflow not found: {WORKFLOW}")

    if not PRODUCTION_PACKAGE.exists():
        raise FileNotFoundError(f"Production package not found: {PRODUCTION_PACKAGE}")

    prompt = load_json(WORKFLOW)

    if LOADER_NODE not in prompt:
        raise RuntimeError(f"Loader node {LOADER_NODE} not found in workflow")

    loader = prompt[LOADER_NODE]

    print("Loader class:", loader.get("class_type"))

    loader["inputs"]["production_package"] = str(PRODUCTION_PACKAGE)
    loader["inputs"]["profile_override"] = "from_package"
    loader["inputs"]["strict_validation"] = True

    payload = {
        "prompt": prompt,
        "client_id": "vscs-known-good-diagnostic",
    }

    request = urllib.request.Request(
        COMFY_URL + "/prompt",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    print()
    print("Submitting workflow to ComfyUI...")

    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print("HTTP ERROR:", exc.code)
        print(exc.read().decode("utf-8", errors="replace"))
        raise

    prompt_id = result["prompt_id"]

    print("Prompt ID:", prompt_id)
    print("Waiting for completion...")
    print()

    while True:
        try:
            with urllib.request.urlopen(COMFY_URL + "/history/" + prompt_id) as response:
                history = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            print("History request failed:", exc)
            time.sleep(3)
            continue

        if prompt_id not in history:
            time.sleep(3)
            continue

        record = history[prompt_id]
        status = record.get("status", {})

        if status.get("completed"):
            print("COMPLETED")
            print("Status:", status.get("status_str"))

            outputs = record.get("outputs", {})
            if outputs:
                print()
                print("Outputs:")
                print(json.dumps(outputs, indent=2))

            print()
            print("Messages:")
            print(json.dumps(status.get("messages", []), indent=2))
            return

        messages = status.get("messages", [])

        for message in messages[-3:]:
            print(message)

        time.sleep(3)


if __name__ == "__main__":
    main()
