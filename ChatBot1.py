from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import os

app = Flask(__name__)

# Verificar e exibir o diretório de trabalho atual
print("Diretório atual:", os.getcwd())

# Carregar os dados fictícios
try:
    base_dir = os.path.dirname(__file__)
    catalogo = pd.read_csv(os.path.join(base_dir, "data", "catalogo_fict.csv"), encoding="latin-1")
    print("Colunas do catálogo:", catalogo.columns.tolist())  # Para depuração
    catalogo['Preco'] = catalogo['Preco'].str.replace(',', '.').astype(float)
    catalogo['Estoque'] = catalogo['Estoque'].astype(int)
    faqs = pd.read_csv(os.path.join(base_dir, "data", "faqs_fict.csv"), encoding="latin-1")
    print("Arquivos carregados com sucesso!")
except UnicodeDecodeError as e:
    print(f"Erro de codificação: {e}")
    exit()
except ValueError as e:
    print(f"Erro de conversão: {e}")
    exit()
except FileNotFoundError as e:
    print(f"Erro: Arquivo não encontrado: {e}")
    exit()

# Inicializar o estado do usuário
user_state = {}

# Função para buscar informações no catálogo
def buscar_produto(produto_nome):
    produto = catalogo[catalogo["Produto"].str.lower() == produto_nome.lower()]
    if not produto.empty:
        try:
            preco = float(produto.iloc[0]['Preco'])
            return (f"{produto.iloc[0]['Produto']} custa R${preco:.2f}. "
                    f"Estoque: {produto.iloc[0]['Estoque']} unidades. "
                    f"Especificações: {produto.iloc[0]['Especificações']}")
        except (ValueError, TypeError) as e:
            print(f"Erro ao formatar preço: {e}")
            return (f"{produto.iloc[0]['Produto']} custa R${produto.iloc[0]['Preço']}. "
                    f"Estoque: {produto.iloc[0]['Estoque']} unidades. "
                    f"Especificações: {produto.iloc[0]['Especificações']}")
    return "Desculpe, não encontrei esse produto. Tente outro, como iPhone 15 ou Galaxy S24."

# Função para buscar respostas nas FAQs
def buscar_faq(pergunta):
    for _, row in faqs.iterrows():
        if any(keyword in pergunta.lower() for keyword in row["Pergunta"].lower().split()):
            return row["Resposta"]
    return "Desculpe, não sei responder isso. Posso ajudar com outra coisa?"

# Função para sugerir upsell
def sugerir_upsell(produto_comprado):
    produto_comprado = produto_comprado.lower()
    if "iphone" in produto_comprado:
        return "Que tal uma Capa iPhone 15 por R$99 para proteger seu novo iPhone? [Sim] [Não]"
    elif "alexa" in produto_comprado:
        return "Você gostaria de um Xiaomi Watch 2 por R$799 para complementar? [Sim] [Não]"
    return "Ótimo! Deseja mais alguma coisa? [Sim] [Não]"

# Rota para receber mensagens do WhatsApp
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        incoming_msg = request.values.get("Body", "").lower().strip()
        from_number = request.values.get("From", "")
        resp = MessagingResponse()
        msg = resp.message()

        # Inicializar o estado do usuário, se necessário
        if from_number not in user_state:
            user_state[from_number] = {"stage": "welcome", "carrinho": [], "produto_atual": ""}

        state = user_state[from_number]

        # Lógica de fluxo conversacional
        if state["stage"] == "welcome":
            msg.body("Olá! Bem-vindo(a) à SavaStore! Estou aqui para ajudar no seu atendimento. "
                     "O que você quer? "
                     "[Preços] [Estoque] [FAQ] [Comprar] [Falar com atendente]")
            state["stage"] = "menu"

        elif state["stage"] == "menu":
            if any(keyword in incoming_msg for keyword in ["preço", "precos", "price"]):
                msg.body("Qual produto você quer saber o preço? (Ex.: iPhone 15, Galaxy S24, Alexa Echo Dot 5)")
                state["stage"] = "buscar_preço"
            elif any(keyword in incoming_msg for keyword in ["estoque", "stock"]):
                msg.body("De qual produto? (Ex.: Apple Watch 9, Xiaomi Watch 2)")
                state["stage"] = "buscar_estoque"
            elif any(keyword in incoming_msg for keyword in ["faq", "duvida", "dúvida", "ajuda"]):
                msg.body("Qual sua dúvida? (Ex.: Como configuro o Alexa?, Entrega é grátis?)")
                state["stage"] = "buscar_faq"
            elif any(keyword in incoming_msg for keyword in ["comprar", "buy"]):
                msg.body(
                    "Ótimo! Escolha o produto: [iPhone 15] [Galaxy S24] [Apple Watch 9] [Alexa Echo Dot 5] [Xiaomi Watch 2]")
                state["stage"] = "comprar"
            elif any(keyword in incoming_msg for keyword in ["falar com atendente", "atendente", "suporte"]):
                msg.body("Ok! Um atendente irá te ajudar em breve. Enquanto isso, posso ajudar com algo mais? [Sim] [Não]")
                state["stage"] = "welcome"
            else:
                msg.body(
                    "Desculpe, não entendi. Escolha uma opção: [Preços] [Estoque] [FAQ] [Comprar] [Falar com atendente]")

        elif state["stage"] == "buscar_preço":
            resposta = buscar_produto(incoming_msg)
            msg.body(resposta + "\nDeseja comprar? [Sim] [Não]")
            state["produto_atual"] = incoming_msg
            state["stage"] = "decidir_compra"

        elif state["stage"] == "buscar_estoque":
            produto = catalogo[catalogo["Produto"].str.lower() == incoming_msg]
            if not produto.empty:
                msg.body(f"Temos {produto.iloc[0]['Estoque']} unidades de {produto.iloc[0]['Produto']} em estoque!")
            else:
                msg.body("Desculpe, não encontrei esse produto.")
            msg.body("O que mais posso ajudar? [Preços] [Estoque] [FAQ] [Comprar] [Falar com atendente]")
            state["stage"] = "menu"

        elif state["stage"] == "buscar_faq":
            resposta = buscar_faq(incoming_msg)
            msg.body(resposta + "\nO que mais posso ajudar? [Preços] [Estoque] [FAQ] [Comprar] [Falar com atendente]")
            state["stage"] = "menu"

        elif state["stage"] == "comprar":
            produto = catalogo[catalogo["Produto"].str.lower() == incoming_msg]
            if not produto.empty:
                state["carrinho"].append(produto.iloc[0]["Produto"])
                state["produto_atual"] = incoming_msg
                msg.body(f"Adicionei {produto.iloc[0]['Produto']} ao carrinho (R${produto.iloc[0]['Preço']:.2f}).")
                msg.body(sugerir_upsell(incoming_msg))
                state["stage"] = "upsell"
            else:
                msg.body(
                    "Desculpe, não encontrei esse produto. Escolha outro: [iPhone 15] [Galaxy S24] [Apple Watch 9] [Alexa Echo Dot 5] [Xiaomi Watch 2]")

        elif state["stage"] == "decidir_compra":
            if any(keyword in incoming_msg for keyword in ["sim", "yes"]):
                produto = catalogo[catalogo["Produto"].str.lower() == state["produto_atual"]]
                state["carrinho"].append(produto.iloc[0]["Produto"])
                msg.body(f"Adicionei {produto.iloc[0]['Produto']} ao carrinho (R${produto.iloc[0]['Preço']:.2f}).")
                msg.body(sugerir_upsell(state["produto_atual"]))
                state["stage"] = "upsell"
            else:
                msg.body("Ok! O que mais posso ajudar? [Preços] [Estoque] [FAQ] [Comprar] [Falar com atendente]")
                state["stage"] = "menu"

        elif state["stage"] == "upsell":
            if any(keyword in incoming_msg for keyword in ["sim", "yes"]):
                if "iphone" in state["produto_atual"].lower():
                    produto_upsell = catalogo[catalogo["Produto"] == "Capa iPhone 15"]
                elif "alexa" in state["produto_atual"].lower():
                    produto_upsell = catalogo[catalogo["Produto"] == "Xiaomi Watch 2"]
                if not produto_upsell.empty:
                    state["carrinho"].append(produto_upsell.iloc[0]["Produto"])
                    total = sum(catalogo[catalogo["Produto"].isin(state["carrinho"])]["Preço"])
                    msg.body(f"Adicionei {produto_upsell.iloc[0]['Produto']} ao carrinho. Total: R${total:.2f}. "
                             "Aqui está o link de pagamento: [link fictício].")
                else:
                    msg.body("Erro ao adicionar upsell. Tente novamente.")
            else:
                total = sum(catalogo[catalogo["Produto"].isin(state["carrinho"])]["Preço"])
                msg.body(f"Ok! Seu total é R${total:.2f}. Aqui está o link de pagamento: [link fictício].")
            msg.body("O que mais posso ajudar? [Preços] [Estoque] [FAQ] [Comprar] [Falar com atendente]")
            state["stage"] = "menu"
            state["carrinho"] = []  # Limpa o carrinho após a compra

        return str(resp)
    except Exception as e:
        print(f"Erro no webhook: {e}")
        resp = MessagingResponse()
        resp.message("Desculpe, houve um erro. Tente novamente ou fale com um atendente.")
        return str(resp)

if __name__ == "__main__":
    app.run(debug=True, port=5000)