from g4f.client import Client

client = Client()

def chatbot_response(user_input):
    response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": user_input}],
    web_search=False
    )

    return response.choices[0].message.content


if __name__ == "__main__":

    pass 
