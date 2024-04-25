from openai import OpenAI

openai_client = OpenAI()

trans_total_prompt_tokens = 0
trans_total_completion_tokens = 0

# s1: temp 0, no system msg, prompt 'Translate to English, replying with only the unquoted translation:\n{text}'
TRANS_SETTINGS = 's1'

# text may contain newlines
def translate_to_en(text):
    prompt = f'Translate to English, replying with only the unquoted translation:\n{text}'
    completion = openai_client.chat.completions.create(
        model='gpt-4',
        messages=[
            # adding a system message strangely makes it non-deterministic, and doesn't seem to improve results
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    global trans_total_prompt_tokens
    global trans_total_completion_tokens
    trans_total_prompt_tokens += completion.usage.prompt_tokens
    trans_total_completion_tokens += completion.usage.completion_tokens

    trans_src = completion.model + ':' + TRANS_SETTINGS

    return completion.choices[0].message.content.strip(), trans_src

if __name__ == '__main__':
    import sys
    print(translate_to_en(sys.stdin.read()))
