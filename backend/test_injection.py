import json
import re

def test_inject():
    with open("doc_dict.json", "r") as f:
        structured_dict = json.load(f)
    with open("markdown_out.md", "r") as f:
        raw_final_text = f.read()

    texts_list = structured_dict.get("texts", [])
    
    # We will accumulate replacements
    # Since raw_final_text might have multiple occurrences, we should be careful.
    
    recovered_prepend = []
    
    for i, item in enumerate(texts_list):
        item_text = item.get("text", "").strip()
        if not item_text:
            continue
        label = item.get("label", "")
        content_layer = item.get("content_layer", "")
        
        if label in ("title", "section_header") and item_text not in raw_final_text:
            recovered_prepend.append(item_text)
        elif content_layer == "furniture" and item_text not in raw_final_text:
            # find preceding text
            prev_text = ""
            for j in range(i - 1, -1, -1):
                prev = texts_list[j].get("text", "").strip()
                if prev and prev in raw_final_text:
                    prev_text = prev
                    break
            
            if prev_text:
                # insert item_text after prev_text in raw_final_text
                # regex replace first occurrence or something?
                # Actually, replace the FIRST occurrence we find, or maybe all?
                # safer: just replace prev_text with prev_text + "\n" + item_text
                print(f"Injecting '{item_text}' after '{prev_text}'")
                raw_final_text = raw_final_text.replace(prev_text, prev_text + "\n\n" + item_text, 1)
            else:
                recovered_prepend.append(item_text)

    if recovered_prepend:
        raw_final_text = "\n\n".join(recovered_prepend) + "\n\n" + raw_final_text

    print("----- NEW TEXT -----")
    print(raw_final_text)

if __name__ == "__main__":
    test_inject()
