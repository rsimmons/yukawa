from openai import OpenAI

openai_client = OpenAI()

# v1: gpt-4-1106-preview, temp 0, no system msg, prompt 'Translate to English, replying with only the unquoted translation:\n{text}'
TRANS_ALGO = 'v1'

# text may contain newlines
def translate_to_en(text):
    prompt = f'Translate to English, replying with only the unquoted translation:\n{text}'
    completion = openai_client.chat.completions.create(
        model='gpt-4-1106-preview',
        messages=[
            # adding a system message strangely makes it non-deterministic, and doesn't seem to improve results
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    return completion.choices[0].message.content.strip()

if __name__ == '__main__':
    import sys
    print(translate_to_en(sys.stdin.read()))
