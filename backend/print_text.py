import fitz
doc = fitz.open('uploads/cv_Shruti_Dhameliya_React_js_Developer_3_Years_of_Exp_f13a7563d127d3a38a427b7b72125f041df1851c9992f6de07a9eca4bc1fbe57.pdf')
text = ""
for page in doc:
    text += page.get_text()
print(text)
