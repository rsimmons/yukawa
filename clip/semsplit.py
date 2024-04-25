import json

from openai import OpenAI

openai_client = OpenAI()

semsplit_total_prompt_tokens = 0
semsplit_total_completion_tokens = 0

def semantic_split_sub_group(subs):
    tools = [
        {
            'type': 'function',
            'function': {
                'name': 'report_split_index',
                'description': 'Report the index at which to split the subtitles',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'index': {
                            'type': 'integer',
                            'description': 'The split index',
                        },
                    },
                },
            },
        },
    ]

    subs_text = ''
    for i, sub in enumerate(subs):
        if i > 0:
            subs_text += '--- %d\n' % i
        subs_text += sub.content + '\n'

    # print('subs_text:')
    # print(subs_text)

    # It was necessary to explicitly tell it to call report_split_index. Using the tool_choice parameter to make it call that would prevent it from explaining its reasoning, which reduces result quality
    prompt = f'At which of these numbered breaks would it be most natural to break these subtitles into two sections, based on the flow of conversation. The goal is that each of the two sections make sense as much as possible on their own. Explain your reasoning, and then report exactly one split index via report_split_index.\n{subs_text}'
    completion = openai_client.chat.completions.create(
        model='gpt-4',
        tools=tools,
        messages=[
            {'role': 'user', 'content': prompt},
        ],
        temperature=0,
    )

    print('semsplit token usage:', completion.usage.prompt_tokens, '+', completion.usage.completion_tokens)
    global semsplit_total_prompt_tokens
    global semsplit_total_completion_tokens
    semsplit_total_prompt_tokens += completion.usage.prompt_tokens
    semsplit_total_completion_tokens += completion.usage.completion_tokens

    choice0 = completion.choices[0]
    print('choices[0]:', choice0)
    assert choice0.finish_reason == 'tool_calls'
    if len(choice0.message.tool_calls) != 1:
        return None
    tc = choice0.message.tool_calls[0]
    assert tc.function.name == 'report_split_index'
    fn_args = json.loads(tc.function.arguments)
    assert fn_args['index'] is not None
    split_idx = fn_args['index']

    return split_idx

# sufficiently compatible with srt.Subtitle
class TestSub:
    def __init__(self, content):
        self.content = content

    def __repr__(self):
        return 'TestSub(content=%r)' % self.content

if __name__ == '__main__':
    # test_subs = [
    #     TestSub(content='お前は 私に\n逆らってるだけなんだろうがな・'),
    #     TestSub(content='それだけじゃ済まんぞ\nどういうことです？'),
    #     TestSub(content='誤判対策室を設立した\n真の意味を知らんだろう'),
    #     TestSub(content='再審請求を棄却するためですか？'),
    #     TestSub(content='死刑制度を存続させるためだよ\n存続？'),
    #     TestSub(content='死刑制度容認は\n８０％を超えてますよ'),
    #     TestSub(content='だが\n死刑制度の機能は低下している'),
    # ]
    # test_subs = [
    #     TestSub(content='「前記 殺害の犯跡を\n隠蔽するため・'),
    #     TestSub(content='前記 長谷川由美が所有する\n同所所在の・'),
    #     TestSub(content='現に人が住居に使用せず\nかつ 現に人がいない・'),
    #     TestSub(content='木造瓦ぶき２階建て家屋を\n焼損しようと企て・'),
    #     TestSub(content='前記 犯行の直後頃・'),
    #     TestSub(content='前記 長谷川方のカーテンに\nサラダ油を染み込ませ・'),
    #     TestSub(content='同カーテンに\n所携のライターで点火し・'),
    #     TestSub(content='火を放ち この火を\n同所の柱等に燃え移らせ・'),
    #     TestSub(content='よって 同家屋を全焼させて\nこれを焼損したものである」'),
    # ]
    # test_subs = [
    #     TestSub(content='圏央道の外回りの\n高尾山インターと・'),
    #     TestSub(content='八王子ジャンクションの間の\n車両火災…'),
    #     TestSub(content='なんか事件？'),
    #     TestSub(content='いや 印鑑詐欺の男が\n見本として使ってたもんです'),
    #     TestSub(content='印鑑詐欺？\nそうです'),
    #     TestSub(content='うちは関係ないぞ'),
    #     TestSub(content='材質 偽って\n高値で販売してたんです'),
    #     TestSub(content='ほう そういうことか\nええ'),
    #     TestSub(content='頼んだのは どんな男でした？'),
    #     TestSub(content='いや 女だよ'),
    #     TestSub(content='女？'),
    #     TestSub(content='これだ'),
    #     TestSub(content='「楠木恵美」'),
    #     TestSub(content='住所を写させてもらいます'),
    # ]
    test_subs = [
        TestSub(content='これどうぞ'),
        TestSub(content='何ですか？'),
        TestSub(content='贈り物だよ'),
        TestSub(content='あっ　ありがとう'),
        # obv split seems here
        TestSub(content='今日いい天気ですね'),
        TestSub(content='そうだね'),
    ]
    print(semantic_split_sub_group(test_subs))
