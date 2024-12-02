import pandas as pd
import glob
import os
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader




def main():
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)

    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )

    authenticator.login()

    if st.session_state["authentication_status"]:
        authenticator.logout()
        # Se o usuário estiver autenticado, exibe a interface principal
        st.write(f'Bem Vindo *{st.session_state["name"]}*')
        st.title("Processamento de Arquivos EFD")
        st.write("Este aplicativo foi desenvolvido para facilitar o processamento de arquivos EFD no formato .txt. Ele realiza a tabulação dos dados extraídos, permitindo que os usuários visualizem as informações em uma tabela organizada diretamente na interface, possibilitando análises resumidas e insights a partir das informações processadas.")

        # Sidebar com input de arquivo
        st.sidebar.image("logo.png", use_container_width=True)
        st.sidebar.title("Configurações")
        uploaded_file = st.sidebar.file_uploader("Selecione o arquivo EFD:", type=["txt"])

        # Botão para processar arquivos
        if st.button("Processar Arquivos"):
            if not uploaded_file:
                st.warning("Por favor, selecione um arquivo EFD para continuar.")
                return

            # Processamento do arquivo selecionado
            try:
                st.write("**Nome do arquivo:**", uploaded_file.name)
                content = uploaded_file.read().decode("ISO-8859-1")
                lines = content.splitlines()  # Dividir conteúdo em linhas
                # Substitua pela sua função de processamento
                linhas_processadas = processar_arquivo(lines)

                if linhas_processadas:
                    df = pd.DataFrame(linhas_processadas)
                    st.write("Tabela de Resultados:")
                    st.dataframe(df, hide_index=True)
                else:
                    st.warning("Nenhum dado foi processado.")

            except Exception as e:
                st.error(f"Erro ao processar o arquivo {uploaded_file.name}: {e}")

    elif st.session_state["authentication_status"] is False:
        st.error('Usuário/Senha is inválido')

    elif st.session_state["authentication_status"] is None:
        st.warning('Por Favor, utilize seu usuário e senha!')
    


def processar_arquivo(linhas):
    participantes = []
    produtos_servicos = []
    linhas_processadas = []
    cabecalho = {}

    for line in linhas:
        if line.startswith('|0000|'):
            cabecalho = processar_cabecalho(line)
        elif line.startswith('|0150|'):
            participantes.append(processar_participante(line))
        elif line.startswith('|0200|'):
            produtos_servicos.append(processar_produtos_servicos(line))

    df_participantes = pd.DataFrame(participantes)
    df_produtos_servicos = pd.DataFrame(produtos_servicos)

    #registro_a100, registro_c100 = None, None
    for line in linhas:
        # Processando registros A100 (Nota Fiscal de Serviço)
        if line.startswith('|A100|'):
            registro_a100 = processar_registro_a100(line, cabecalho, df_participantes)
        elif line.startswith('|A170|') and registro_a100:
            linha_processada = processar_registro_a170(line, registro_a100, df_produtos_servicos)
            if linha_processada:
                linhas_processadas.append(linha_processada)
        
        # Processando registros A170 (Itens da Nota Fiscal de Serviço)
        elif line.startswith('|C100|'):
            registro_c100 = processar_registro_c100(line, cabecalho, df_participantes)
        elif line.startswith('|C170|') and registro_c100:
            linha_processada = processar_registro_c170(line, registro_c100, df_produtos_servicos)
            if linha_processada:
                linhas_processadas.append(linha_processada)
        
        # Processando registros C500 (Nota Fiscal contas Agua Luz Gas)
        elif line.startswith('|C500|'):
            registro_c500 = processar_registro_c500(line, cabecalho, df_participantes)
        elif line.startswith('|C501|'):
            registro_c501 = processar_registro_c501(line, registro_c500)
        elif line.startswith('|C505|'):
            registro_c505 = processar_registro_c505(line, registro_c501)
            if registro_c505:
                linhas_processadas.append(registro_c505)
        
        # Processando registros D100 (Aquisição de Seviço de Tranporte)
        elif line.startswith('|D100|'):
            registro_d100,vl_icms, bc_icms = processar_registro_d100(line, cabecalho, df_participantes)
        elif line.startswith('|D101|'):
            registro_d101 = processar_registro_d101(line, registro_d100, vl_icms, bc_icms)
        elif line.startswith('|D105|'):
            registro_d105 = processar_registro_d105(line, registro_d101)
            if registro_d105:
                linhas_processadas.append(registro_d105)
        
        # Processando registros D200 (Nota Fiscal de Seviço de Tranporte)
        elif line.startswith('|D200|'):
            registro_d200, cfop = processar_registro_d200(line, cabecalho)
        elif line.startswith('|D201|'):
            registro_d201,cst_pis,bc_pis,ali_pis,vl_pis = processar_registro_d201(line, registro_d200, cfop)   
        elif line.startswith('|D205|'):
            registro_d205 = processar_registro_d205(line, registro_d201,cst_pis,bc_pis,ali_pis,vl_pis)
            if registro_d205:
                linhas_processadas.append(registro_d205)
        
        # Processando registros D500 (Nota Fiscal Comunicação)
        elif line.startswith('|D500|'):
            registro_d500 = processar_registro_d500(line, cabecalho, df_participantes)
        elif line.startswith('|D501|'):
            registro_d501 = processar_registro_d501(line, registro_d500)
        elif line.startswith('|D505|'):
            registro_d505 = processar_registro_d505(line, registro_d501)
            if registro_d505:
                linhas_processadas.append(registro_d505)
        
        #Demais Documentos e Operações
        elif line.startswith('|F100|'):
            registro_f100 = processar_registro_f100(line, cabecalho)
            if registro_f100:
                linhas_processadas.append(registro_f100)


    return linhas_processadas

# Funções auxiliares
def define_enumeradores(tipo, valor):
    if tipo == "Tipo Operação":       
        data = {
            0: "0 - Entrada",
            1: "1 - Saída",
        }
        return data.get(valor, "Opção inválida")
    elif tipo == "Situação":
        data = {
            0: "00 - Documento regular",
            1: "02 - Documento cancelado",
        }
        return data.get(valor, "Opção inválida")
    elif tipo == "UF":
        data = {
            12: "AC",  # Acre
            27: "AL",  # Alagoas
            13: "AM",  # Amazonas
            16: "AP",  # Amapá
            29: "BA",  # Bahia
            23: "CE",  # Ceará
            53: "DF",  # Distrito Federal
            32: "ES",  # Espírito Santo
            52: "GO",  # Goiás
            21: "MA",  # Maranhão
            31: "MG",  # Minas Gerais
            50: "MS",  # Mato Grosso do Sul
            51: "MT",  # Mato Grosso
            15: "PA",  # Pará
            25: "PB",  # Paraíba
            26: "PE",  # Pernambuco
            22: "PI",  # Piauí
            41: "PR",  # Paraná
            33: "RJ",  # Rio de Janeiro
            24: "RN",  # Rio Grande do Norte
            43: "RS",  # Rio Grande do Sul
            11: "RO",  # Rondônia
            14: "RR",  # Roraima
            42: "SC",  # Santa Catarina
            35: "SP",  # São Paulo
            28: "SE",  # Sergipe
            17: "TO",  # Tocantins
        }
        return data.get(valor, "Opção inválida")

def formatar_data(valor):
    try:
        return f"{valor[:2]}/{valor[2:4]}/{valor[4:]}" 
    except:
        return None

def processar_cabecalho(line):
    arq = line.split("|")
    return {
        'CNPJ': arq[9].strip(),
        'Período': formatar_data(arq[6]),
        'ANO': arq[6][4:8],
    }

def processar_participante(line):
    campos = line.split('|')
    try:
        return {
            'Código': campos[2],  
            'Nome': campos[3].replace(';',''),
            'CNPJ': campos[5],  
            'CPF': campos[6],
            'Código Municipio': campos[8],
        }
    except:
        return {
            'Código': '',  
            'Nome': '',
            'CNPJ': '',  
            'CPF': '',
            'Código Municipio': '',
        }

def processar_produtos_servicos(line):
    campos = line.split('|')
    try:
        return {
            'Código': campos[2],  
            'Descrição': campos[3].replace(';',''),
            'Código Barra': campos[4],  
            'Tipo': campos[7],
            'Código NCM': campos[8],
            'Código Serviço': campos[11],
            'Aliquota ICMS': campos[12],
            'Unidade Medida': campos[6],
        }
    except IndexError:
        return None

def processar_registro_a100(line, cabecalho, df_participantes):
    campos = line.split('|')
    try:
        return {
            **cabecalho,
            'Registros': 'A100/A170 - Nota Fiscal de Serviço',
            'Tipo Operação': define_enumeradores('Tipo Operação',int(campos[2])),
            'Situação': define_enumeradores('Situação',int(campos[5])),
            'Código Participante': campos[4],
            'CNPJ Participante': df_participantes[df_participantes['Código'] == campos[4]]['CNPJ'].values[0],
            'CPF Participante': df_participantes[df_participantes['Código'] == campos[4]]['CPF'].values[0],
            'Nome Participante': df_participantes[df_participantes['Código'] == campos[4]]['Nome'].values[0],
            'UF Origem/Destino': define_enumeradores('UF',int(df_participantes[df_participantes['Código'] == campos[4]]['Código Municipio'].values[0][:2]))+"/"+define_enumeradores('UF',int(df_participantes[df_participantes['Código'] == campos[4]]['Código Municipio'].values[0][:2])),
            'Número Documento': campos[8],
            'Série': campos[6],
            'Chave NF-e': campos[9],
            'Data Documento': formatar_data(campos[10]),
            'Data Entrada/Saída': formatar_data(campos[11]),
            'Vlr Documento': campos[12],
            'Vlr Desconto NF': campos[14],
            'Vlr Mercadoria/Operação': '',
            'Vlr Frete': '',
            'Vlr ISSQN': campos[21]
        }
    except IndexError:
        print(f"Linha A100 inválida: {line}")
        return None

def processar_registro_a170(line, pai, df_produtos_servicos):
    campos = line.split('|')
    try:
        return {
            **pai,
            'Número Item': campos[2],
            'Código Item': campos[3],
            'Descrição Complementar': campos[4].replace(';',''),
            'Descrição Item': df_produtos_servicos[df_produtos_servicos['Código'] == campos[3]]['Descrição'].values[0],
            'NCM': df_produtos_servicos[df_produtos_servicos['Código'] == campos[3]]['Código NCM'].values[0],
            'Código Serviço': df_produtos_servicos[df_produtos_servicos['Código'] == campos[3]]['Código Serviço'].values[0],
            'Código Barra': df_produtos_servicos[df_produtos_servicos['Código'] == campos[3]]['Código Barra'].values[0],
            'Tipo Item': df_produtos_servicos[df_produtos_servicos['Código'] == campos[3]]['Tipo'].values[0],
            'Vlr Item': campos[5],
            'Qtde': '',
            'Unidade Medida': df_produtos_servicos[df_produtos_servicos['Código'] == campos[3]]['Unidade Medida'].values[0],
            'Vlr Desconto Item': campos[6],
            'Natureza Crédito': campos[7],
            'CFOP': '',
            'CFOP Faturamento': '',
            'CST ICMS': '',
            'Vlr Base Cálculo ICMS': '',
            'Alíquota ICMS': '',
            'Vlr ICMS': '',
            'Vlr Base Cálculo ICMS ST': '',
            'Alíquota ICMS ST': '',
            'Vlr ICMS ST': '',
            'CST IPI': '',
            'Vlr Base Cálculo IPI': '',
            'Alíquota IPI': '',
            'Vlr IPI': '',
            'pis/cofins': str(float(campos[12])+float(campos[16])).replace(".",","),
            'CST PIS': campos[9],
            'Vlr Base Cálculo PIS': campos[10],
            'Qtde Base Cálculo PIS': '',
            'Alíquota PIS': campos[11],
            'Qtde Alíquota PIS': '',
            'Vlr PIS': campos[12],
            'CST Cofins': campos[13],
            'Vlr Base Cálculo Cofins': campos[14],
            'Qtde Base Cálculo Cofins': '',
            'Alíquota Cofins': campos[15],
            'Qtde Alíquota Cofins': '',
            'Vlr Cofins': campos[16],
            'Conta Contábil': campos[17],
            'Débito/Crédito': '',
        }
    except IndexError:
        print(f"Linha A170 inválida: {line}")
        return None    

def processar_registro_c100(line, cabecalho, df_participantes):
    campos = line.split('|')
    try:
        return {
            **cabecalho,
            'Registros': 'C100/C170 - Documento - Nota Fiscal',
            'Tipo Operação': define_enumeradores('Tipo Operação',int(campos[2])),
            'Situação': define_enumeradores('Situação',int(campos[6])),
            'Código Participante': campos[4],
            'CNPJ Participante': df_participantes[df_participantes['Código'] == campos[4]]['CNPJ'].values[0],
            'CPF Participante': df_participantes[df_participantes['Código'] == campos[4]]['CPF'].values[0],
            'Nome Participante': df_participantes[df_participantes['Código'] == campos[4]]['Nome'].values[0],
            'UF Origem/Destino': define_enumeradores('UF',int(df_participantes[df_participantes['Código'] == campos[4]]['Código Municipio'].values[0][:2]))+"/"+define_enumeradores('UF',int(df_participantes[df_participantes['Código'] == campos[4]]['Código Municipio'].values[0][:2])),
            'Número Documento': campos[8],
            'Série': campos[7],
            'Chave NF-e': campos[9],
            'Data Documento': formatar_data(campos[10]),
            'Data Entrada/Saída': formatar_data(campos[11]),
            'Vlr Documento': campos[12],
            'Vlr Desconto NF': campos[14],
            'Vlr Mercadoria/Operação': campos[16],
            'Vlr Frete': campos[18],
            'Vlr ISSQN': '',
        }
    except Exception as e:
        print(f"Linha C100 inválida: {line} - {e}")
        return None

def processar_registro_c170(line, pai, df_produtos_servicos):
    campos = line.split('|')
    try:
        return {
            **pai,
            'Número Item': campos[2],
            'Código Item': campos[3],
            'Descrição Complementar': campos[4].replace(';',''),
            'Descrição Item': df_produtos_servicos[df_produtos_servicos['Código'] == campos[3]]['Descrição'].values[0],
            'NCM': df_produtos_servicos[df_produtos_servicos['Código'] == campos[3]]['Código NCM'].values[0],
            'Código Serviço': df_produtos_servicos[df_produtos_servicos['Código'] == campos[3]]['Código Serviço'].values[0],
            'Código Barra': df_produtos_servicos[df_produtos_servicos['Código'] == campos[3]]['Código Barra'].values[0],
            'Tipo Item': df_produtos_servicos[df_produtos_servicos['Código'] == campos[3]]['Tipo'].values[0],
            'Vlr Item': campos[7],
            'Qtde': campos[5],
            'Unidade Medida': campos[6],
            'Vlr Desconto Item': campos[8],
            'Natureza Crédito': campos[12],
            'CFOP': campos[11],
            'CFOP Faturamento': '',
            'CST ICMS': campos[10],
            'Vlr Base Cálculo ICMS': campos[13],
            'Alíquota ICMS': campos[14],
            'Vlr ICMS': campos[15],
            'Vlr Base Cálculo ICMS ST': campos[16],
            'Alíquota ICMS ST': campos[17],
            'Vlr ICMS ST': campos[18],
            'CST IPI': campos[20],
            'Vlr Base Cálculo IPI': campos[22],
            'Alíquota IPI': campos[23],
            'Vlr IPI': campos[24],
            'pis/cofins': str(float(campos[30])+float(campos[36])).replace(".",","),
            'CST PIS': campos[25],
            'Vlr Base Cálculo PIS': campos[26],
            'Qtde Base Cálculo PIS': campos[28],
            'Alíquota PIS': campos[27],
            'Qtde Alíquota PIS': campos[29],
            'Vlr PIS': campos[30],
            'CST Cofins': campos[31],
            'Vlr Base Cálculo Cofins': campos[32],
            'Qtde Base Cálculo Cofins': campos[34],
            'Alíquota Cofins': campos[33],
            'Qtde Alíquota Cofins': campos[35],
            'Vlr Cofins': campos[36],
            'Conta Contábil': campos[37],
            'Débito/Crédito': '',
        }
    except:
        return {
            **pai,
            'Número Item': '',
            'Código Item': '',
            'Descrição Complementar': '',
            'Descrição Item': '',
            'NCM': '',
            'Código Serviço': '',
            'Código Barra': '',
            'Tipo Item': '',
            'Vlr Item': '',
            'Qtde': '',
            'Unidade Medida': '',
            'Vlr Desconto Item': '',
            'Natureza Crédito': '',
            'CFOP': '',
            'CFOP Faturamento': '',
            'CST ICMS': '',
            'Vlr Base Cálculo ICMS': '',
            'Alíquota ICMS': '',
            'Vlr ICMS': '',
            'Vlr Base Cálculo ICMS ST': '',
            'Alíquota ICMS ST': '',
            'Vlr ICMS ST': '',
            'CST IPI': '',
            'Vlr Base Cálculo IPI': '',
            'Alíquota IPI': '',
            'Vlr IPI': '',
            'pis/cofins': '',
            'CST PIS': '',
            'Vlr Base Cálculo PIS': '',
            'Qtde Base Cálculo PIS': '',
            'Alíquota PIS': '',
            'Qtde Alíquota PIS': '',
            'Vlr PIS': '',
            'CST Cofins': '',
            'Vlr Base Cálculo Cofins': '',
            'Qtde Base Cálculo Cofins': '',
            'Alíquota Cofins': '',
            'Qtde Alíquota Cofins': '',
            'Vlr Cofins': '',
            'Conta Contábil': '',
            'Débito/Crédito': '',
        }

def processar_registro_c500(line, cabecalho, df_participantes):
    campos = line.split('|')
    try:
        return {
            **cabecalho,
            'Registros': 'C500/C505 - Nota Fiscal/Conta de Energia Elétrica/Água/Gás',
            'Tipo Operação': define_enumeradores('Tipo Operação', 0),
            'Situação': define_enumeradores('Situação',int(campos[4])),
            'Código Participante': campos[2],
            'CNPJ Participante': df_participantes[df_participantes['Código'] == campos[2]]['CNPJ'].values[0],
            'CPF Participante': df_participantes[df_participantes['Código'] == campos[2]]['CPF'].values[0],
            'Nome Participante': df_participantes[df_participantes['Código'] == campos[2]]['Nome'].values[0],
            'UF Origem/Destino': define_enumeradores('UF',int(df_participantes[df_participantes['Código'] == campos[2]]['Código Municipio'].values[0][:2]))+"/"+define_enumeradores('UF',int(df_participantes[df_participantes['Código'] == campos[2]]['Código Municipio'].values[0][:2])),
            'Número Documento': campos[7],
            'Série': campos[5],
            'Chave NF-e': '',
            'Data Documento': formatar_data(campos[8]),
            'Data Entrada/Saída': formatar_data(campos[9]),
            'Vlr Documento': campos[10],
            'Vlr Desconto NF': '',
            'Vlr Mercadoria/Operação': '',
            'Vlr Frete': '',
            'Vlr ISSQN': '',
        }
    except Exception as e:
        print(f"Linha C500 inválida: {line} - {e}")
        return None

def processar_registro_c501(line, pai):
    campos = line.split('|')
    try:
        return {
            **pai,
            'Número Item': '',
            'Código Item': '',
            'Descrição Complementar': '',
            'Descrição Item': '',
            'NCM': '',
            'Código Serviço': '',
            'Código Barra': '',
            'Tipo Item': '',
            'Vlr Item': campos[3],
            'Qtde': '',
            'Unidade Medida': '',
            'Vlr Desconto Item': '',
            'Natureza Crédito': campos[4],
            'CFOP': '',
            'CFOP Faturamento': '',
            'CST ICMS': '',
            'Vlr Base Cálculo ICMS': '',
            'Alíquota ICMS': '',
            'Vlr ICMS': '',
            'Vlr Base Cálculo ICMS ST':'',
            'Alíquota ICMS ST': '',
            'Vlr ICMS ST': '',
            'CST IPI': '',
            'Vlr Base Cálculo IPI': '',
            'Alíquota IPI': '',
            'Vlr IPI': '',
            'pis/cofins': '',
            'CST PIS': campos[2],
            'Vlr Base Cálculo PIS': campos[5],
            'Qtde Base Cálculo PIS': '',
            'Alíquota PIS': campos[6],
            'Qtde Alíquota PIS': '',
            'Vlr PIS': campos[7],
        }
    except:
        return {
            **pai,
            'Número Item': '',
            'Código Item': '',
            'Descrição Complementar': '',
            'Descrição Item': '',
            'NCM': '',
            'Código Serviço': '',
            'Código Barra': '',
            'Tipo Item': '',
            'Vlr Item': '',
            'Qtde': '',
            'Unidade Medida': '',
            'Vlr Desconto Item': '',
            'Natureza Crédito': '',
            'CFOP': '',
            'CFOP Faturamento': '',
            'CST ICMS': '',
            'Vlr Base Cálculo ICMS': '',
            'Alíquota ICMS': '',
            'Vlr ICMS': '',
            'Vlr Base Cálculo ICMS ST': '',
            'Alíquota ICMS ST': '',
            'Vlr ICMS ST': '',
            'CST IPI': '',
            'Vlr Base Cálculo IPI': '',
            'Alíquota IPI': '',
            'Vlr IPI': '',
            'pis/cofins': '',
            'CST PIS': '',
            'Vlr Base Cálculo PIS': '',
            'Qtde Base Cálculo PIS': '',
            'Alíquota PIS': '',
            'Qtde Alíquota PIS': '',
            'Vlr PIS': '',
        }

def processar_registro_c505(line, pai):
    campos = line.split('|')
    try:
        return {
            **pai,
            'CST Cofins': campos[2],
            'Vlr Base Cálculo Cofins': campos[5],
            'Qtde Base Cálculo Cofins': '',
            'Alíquota Cofins': campos[6],
            'Qtde Alíquota Cofins': '',
            'Vlr Cofins': campos[7],
            'Conta Contábil': campos[8],
            'Débito/Crédito': '',
        }
    except:
        return {
            **pai,
            'CST Cofins': '',
            'Vlr Base Cálculo Cofins': '',
            'Qtde Base Cálculo Cofins': '',
            'Alíquota Cofins': '',
            'Qtde Alíquota Cofins': '',
            'Vlr Cofins': '',
            'Conta Contábil': '',
            'Débito/Crédito': '',
        }

def processar_registro_d100(line, cabecalho, df_participantes):
    campos = line.split('|')
    try:
        return {
            **cabecalho,
            'Registros': 'D100/D105 - Aquisição de Serviços de Transporte',
            'Tipo Operação': define_enumeradores('Tipo Operação',int(campos[2])),
            'Situação': define_enumeradores('Situação',int(campos[6])),
            'Código Participante': campos[4],
            'CNPJ Participante': df_participantes[df_participantes['Código'] == campos[4]]['CNPJ'].values[0],
            'CPF Participante': df_participantes[df_participantes['Código'] == campos[4]]['CPF'].values[0],
            'Nome Participante': df_participantes[df_participantes['Código'] == campos[4]]['Nome'].values[0],
            'UF Origem/Destino': define_enumeradores('UF',int(df_participantes[df_participantes['Código'] == campos[4]]['Código Municipio'].values[0][:2]))+"/"+define_enumeradores('UF',int(df_participantes[df_participantes['Código'] == campos[4]]['Código Municipio'].values[0][:2])),
            'Número Documento': campos[9],
            'Série': campos[7],
            'Chave NF-e': campos[10],
            'Data Documento': formatar_data(campos[11]),
            'Data Entrada/Saída': formatar_data(campos[12]),
            'Vlr Documento': campos[15],
            'Vlr Desconto NF': campos[16],
            'Vlr Mercadoria/Operação': campos[18],
            'Vlr Frete': '',
            'Vlr ISSQN': '',
        },campos[20],campos[19]
    except Exception as e:
        print(f"Linha D100 inválida: {line} - {e}")
        return None

def processar_registro_d101(line, pai, vl_icms, bc_icms):
    campos = line.split('|')
    try:
        return {
            **pai,
            'Número Item': '',
            'Código Item': '',
            'Descrição Complementar': '',
            'Descrição Item': '',
            'NCM': '',
            'Código Serviço': '',
            'Código Barra': '',
            'Tipo Item': '',
            'Vlr Item': campos[3],
            'Qtde': '',
            'Unidade Medida': '',
            'Vlr Desconto Item': '',
            'Natureza Crédito': campos[5],
            'CFOP': '',
            'CFOP Faturamento': '',
            'CST ICMS': '',
            'Vlr Base Cálculo ICMS': bc_icms,
            'Alíquota ICMS': '',
            'Vlr ICMS': vl_icms,
            'Vlr Base Cálculo ICMS ST': '',
            'Alíquota ICMS ST': '',
            'Vlr ICMS ST': '',
            'CST IPI': '',
            'Vlr Base Cálculo IPI': '',
            'Alíquota IPI': '',
            'Vlr IPI': '',
            'pis/cofins': '',
            'CST PIS': campos[4],
            'Vlr Base Cálculo PIS': campos[6],
            'Qtde Base Cálculo PIS': '',
            'Alíquota PIS': campos[7],
            'Qtde Alíquota PIS': '',
            'Vlr PIS': campos[8],
        }
    except:
        return {
            **pai,
            'Número Item': '',
            'Código Item': '',
            'Descrição Complementar': '',
            'Descrição Item': '',
            'NCM': '',
            'Código Serviço': '',
            'Código Barra': '',
            'Tipo Item': '',
            'Vlr Item': '',
            'Qtde': '',
            'Unidade Medida': '',
            'Vlr Desconto Item': '',
            'Natureza Crédito': '',
            'CFOP': '',
            'CFOP Faturamento': '',
            'CST ICMS': '',
            'Vlr Base Cálculo ICMS': '',
            'Alíquota ICMS': '',
            'Vlr ICMS': '',
            'Vlr Base Cálculo ICMS ST': '',
            'Alíquota ICMS ST': '',
            'Vlr ICMS ST': '',
            'CST IPI': '',
            'Vlr Base Cálculo IPI': '',
            'Alíquota IPI': '',
            'Vlr IPI': '',
            'pis/cofins': '',
            'CST PIS': '',
            'Vlr Base Cálculo PIS': '',
            'Qtde Base Cálculo PIS': '',
            'Alíquota PIS': '',
            'Qtde Alíquota PIS': '',
            'Vlr PIS': '',
        }

def processar_registro_d105(line, pai):
    campos = line.split('|')
    try:
        return {
            **pai,
            'CST Cofins': campos[4],
            'Vlr Base Cálculo Cofins': campos[6],
            'Qtde Base Cálculo Cofins': '',
            'Alíquota Cofins': campos[7],
            'Qtde Alíquota Cofins': '',
            'Vlr Cofins': campos[8],
            'Conta Contábil': campos[9],
            'Débito/Crédito': '',
        }
    except:
        return {
            **pai,
            'CST Cofins': '',
            'Vlr Base Cálculo Cofins': '',
            'Qtde Base Cálculo Cofins': '',
            'Alíquota Cofins': '',
            'Qtde Alíquota Cofins': '',
            'Vlr Cofins': '',
            'Conta Contábil': '',
            'Débito/Crédito': '',
        }

def processar_registro_d200(line, cabecalho):
    campos = line.split('|')
    try:
        return {
            **cabecalho,
            'Registros': 'D200/D205 - Resumo Diário - Nota Fiscal de Serviço de Transporte',
            'Tipo Operação': define_enumeradores('Tipo Operação', 1),
            'Situação': '',
            'Código Participante': '',
            'CNPJ Participante': '',
            'CPF Participante': '',
            'Nome Participante': '',
            'UF Origem/Destino': '',
            'Número Documento': campos[6],
            'Série': campos[4],
            'Chave NF-e': '',
            'Data Documento': formatar_data(campos[9]),
            'Data Entrada/Saída': '',
            'Vlr Documento': campos[10],
            'Vlr Desconto NF': campos[11],
            'Vlr Mercadoria/Operação': '',
            'Vlr Frete': '',
            'Vlr ISSQN': '',
        },campos[8]
    except Exception as e:
        print(f"Linha D200 inválida: {line} - {e}")
        return None

def processar_registro_d201(line, pai, cfop):
    campos = line.split('|')
    try:
        return {
            **pai,
            'Número Item': '',
            'Código Item': '',
            'Descrição Complementar': '',
            'Descrição Item': '',
            'NCM': '',
            'Código Serviço': '',
            'Código Barra': '',
            'Tipo Item': '',
            'Vlr Item': campos[3],
            'Qtde': '',
            'Unidade Medida': '',
            'Vlr Desconto Item': '',
            'Natureza Crédito': '',
            'CFOP': cfop,
            'CFOP Faturamento': 'Faturamento',
            'CST ICMS': '',
            'Vlr Base Cálculo ICMS': '',
            'Alíquota ICMS': '',
            'Vlr ICMS': '',
            'Vlr Base Cálculo ICMS ST': '',
            'Alíquota ICMS ST': '',
            'Vlr ICMS ST': '',
            'CST IPI': '',
            'Vlr Base Cálculo IPI': '',
            'Alíquota IPI': '',
            'Vlr IPI': '',
        },campos[2],campos[4],campos[5],campos[6]
    except:
        return {
            **pai,
            'Número Item': '',
            'Código Item': '',
            'Descrição Complementar': '',
            'Descrição Item': '',
            'NCM': '',
            'Código Serviço': '',
            'Código Barra': '',
            'Tipo Item': '',
            'Vlr Item': '',
            'Qtde': '',
            'Unidade Medida': '',
            'Vlr Desconto Item': '',
            'Natureza Crédito': '',
            'CFOP': '',
            'CFOP Faturamento': '',
            'CST ICMS': '',
            'Vlr Base Cálculo ICMS': '',
            'Alíquota ICMS': '',
            'Vlr ICMS': '',
            'Vlr Base Cálculo ICMS ST': '',
            'Alíquota ICMS ST': '',
            'Vlr ICMS ST': '',
            'CST IPI': '',
            'Vlr Base Cálculo IPI': '',
            'Alíquota IPI': '',
            'Vlr IPI': '',
        },'','','',''

def processar_registro_d205(line, pai, cst_pis, bc_pis, ali_pis, vl_pis):
    campos = line.split('|')
    try:
        return {
            **pai,
            'pis/cofins': str(float(vl_pis)+float(campos[6])).replace(".",","),
            'CST PIS': cst_pis,
            'Vlr Base Cálculo PIS': bc_pis,
            'Qtde Base Cálculo PIS': '',
            'Alíquota PIS': ali_pis,
            'Qtde Alíquota PIS': '',
            'Vlr PIS': vl_pis,
            'CST Cofins': campos[2],
            'Vlr Base Cálculo Cofins': campos[4],
            'Qtde Base Cálculo Cofins': '',
            'Alíquota Cofins': campos[5],
            'Qtde Alíquota Cofins': '',
            'Vlr Cofins': campos[6],
            'Conta Contábil': campos[7],
            'Débito/Crédito': '',
        }
    except:
        return {
            **pai,
            'pis/cofins': '',
            'CST PIS': campos[4],
            'Vlr Base Cálculo PIS': campos[6],
            'Qtde Base Cálculo PIS': '',
            'Alíquota PIS': campos[7],
            'Qtde Alíquota PIS': '',
            'Vlr PIS': campos[8],
            'CST Cofins': '',
            'Vlr Base Cálculo Cofins': '',
            'Qtde Base Cálculo Cofins': '',
            'Alíquota Cofins': '',
            'Qtde Alíquota Cofins': '',
            'Vlr Cofins': '',
            'Conta Contábil': '',
            'Débito/Crédito': '',
        }

def processar_registro_d500(line, cabecalho, df_participantes):
    campos = line.split('|')
    try:
        return {
            **cabecalho,
            'Registros': 'D500/D505 - Nota Fiscal de Serviço de Comunicação',
            'Tipo Operação': define_enumeradores('Tipo Operação', int(campos[2])),
            'Situação': define_enumeradores('Situação',int(campos[6])),
            'Código Participante': campos[4],
            'CNPJ Participante': df_participantes[df_participantes['Código'] == campos[4]]['CNPJ'].values[0],
            'CPF Participante': df_participantes[df_participantes['Código'] == campos[4]]['CPF'].values[0],
            'Nome Participante': df_participantes[df_participantes['Código'] == campos[4]]['Nome'].values[0],
            'UF Origem/Destino': define_enumeradores('UF',int(df_participantes[df_participantes['Código'] == campos[4]]['Código Municipio'].values[0][:2]))+"/"+define_enumeradores('UF',int(df_participantes[df_participantes['Código'] == campos[4]]['Código Municipio'].values[0][:2])),
            'Número Documento': campos[9],
            'Série': campos[7],
            'Chave NF-e': '',
            'Data Documento': formatar_data(campos[10]),
            'Data Entrada/Saída': formatar_data(campos[11]),
            'Vlr Documento': campos[12],
            'Vlr Desconto NF': campos[13],
            'Vlr Mercadoria/Operação': campos[14],
            'Vlr Frete': '',
            'Vlr ISSQN': '',
        }
    except Exception as e:
        print(f"Linha D500 inválida: {line} - {e}")
        return None

def processar_registro_d501(line, pai):
    campos = line.split('|')
    try:
        return {
            **pai,
            'Número Item': '',
            'Código Item': '',
            'Descrição Complementar': '',
            'Descrição Item': '',
            'NCM': '',
            'Código Serviço': '',
            'Código Barra': '',
            'Tipo Item': '',
            'Vlr Item': campos[3],
            'Qtde': '',
            'Unidade Medida': '',
            'Vlr Desconto Item': '',
            'Natureza Crédito': campos[4],
            'CFOP': '',
            'CFOP Faturamento': '',
            'CST ICMS': '',
            'Vlr Base Cálculo ICMS': '',
            'Alíquota ICMS': '',
            'Vlr ICMS': '',
            'Vlr Base Cálculo ICMS ST':'',
            'Alíquota ICMS ST': '',
            'Vlr ICMS ST': '',
            'CST IPI': '',
            'Vlr Base Cálculo IPI': '',
            'Alíquota IPI': '',
            'Vlr IPI': '',
            'pis/cofins': '',
            'CST PIS': campos[2],
            'Vlr Base Cálculo PIS': campos[5],
            'Qtde Base Cálculo PIS': '',
            'Alíquota PIS': campos[6],
            'Qtde Alíquota PIS': '',
            'Vlr PIS': campos[7],
        }
    except:
        return {
            **pai,
            'Número Item': '',
            'Código Item': '',
            'Descrição Complementar': '',
            'Descrição Item': '',
            'NCM': '',
            'Código Serviço': '',
            'Código Barra': '',
            'Tipo Item': '',
            'Vlr Item': '',
            'Qtde': '',
            'Unidade Medida': '',
            'Vlr Desconto Item': '',
            'Natureza Crédito': '',
            'CFOP': '',
            'CFOP Faturamento': '',
            'CST ICMS': '',
            'Vlr Base Cálculo ICMS': '',
            'Alíquota ICMS': '',
            'Vlr ICMS': '',
            'Vlr Base Cálculo ICMS ST': '',
            'Alíquota ICMS ST': '',
            'Vlr ICMS ST': '',
            'CST IPI': '',
            'Vlr Base Cálculo IPI': '',
            'Alíquota IPI': '',
            'Vlr IPI': '',
            'pis/cofins': '',
            'CST PIS': '',
            'Vlr Base Cálculo PIS': '',
            'Qtde Base Cálculo PIS': '',
            'Alíquota PIS': '',
            'Qtde Alíquota PIS': '',
            'Vlr PIS': '',
        }

def processar_registro_d505(line, pai):
    campos = line.split('|')
    try:
        return {
            **pai,
            'CST Cofins': campos[2],
            'Vlr Base Cálculo Cofins': campos[5],
            'Qtde Base Cálculo Cofins': '',
            'Alíquota Cofins': campos[6],
            'Qtde Alíquota Cofins': '',
            'Vlr Cofins': campos[7],
            'Conta Contábil': campos[8],
            'Débito/Crédito': '',
        }
    except:
        return {
            **pai,
            'CST Cofins': '',
            'Vlr Base Cálculo Cofins': '',
            'Qtde Base Cálculo Cofins': '',
            'Alíquota Cofins': '',
            'Qtde Alíquota Cofins': '',
            'Vlr Cofins': '',
            'Conta Contábil': '',
            'Débito/Crédito': '',
        }

def processar_registro_f100(line, cabecalho):
    campos = line.split('|')
    try:
        return {
            **cabecalho,
            'Registros': 'F100 - Demais Documentos e Operações',
            'Tipo Operação': define_enumeradores('Tipo Operação',1),
            'Situação': '',
            'Código Participante': '',
            'CNPJ Participante': '',
            'CPF Participante': '',
            'Nome Participante': '',
            'UF Origem/Destino': '',
            'Número Documento': '',
            'Série': '',
            'Chave NF-e': '',
            'Data Documento': formatar_data(campos[5]),
            'Data Entrada/Saída': '',
            'Vlr Documento': campos[6],
            'Vlr Desconto NF': '',
            'Vlr Mercadoria/Operação': '',
            'Vlr Frete': '',
            'Vlr ISSQN': '',
            'Número Item': '',
            'Código Item': '',
            'Descrição Complementar': '',
            'Descrição Item': '',
            'NCM': '',
            'Código Serviço': '',
            'Código Barra': '',
            'Tipo Item': '',
            'Vlr Item': campos[6],
            'Qtde': '',
            'Unidade Medida': '',
            'Vlr Desconto Item': '',
            'Natureza Crédito': campos[15],
            'CFOP': '',
            'CFOP Faturamento': '',
            'CST ICMS': '',
            'Vlr Base Cálculo ICMS': '',
            'Alíquota ICMS': '',
            'Vlr ICMS': '',
            'Vlr Base Cálculo ICMS ST': '',
            'Alíquota ICMS ST': '',
            'Vlr ICMS ST': '',
            'CST IPI': '',
            'Vlr Base Cálculo IPI': '',
            'Alíquota IPI': '',
            'Vlr IPI': '',
            'pis/cofins': str(float(campos[10].replace(",","."))+float(campos[14].replace(",","."))).replace(".",","),
            'CST PIS': campos[7],
            'Vlr Base Cálculo PIS': campos[8],
            'Qtde Base Cálculo PIS': '',
            'Alíquota PIS': campos[9],
            'Qtde Alíquota PIS': '',
            'Vlr PIS': campos[10],
            'CST Cofins': campos[11],
            'Vlr Base Cálculo Cofins': campos[12],
            'Qtde Base Cálculo Cofins': '',
            'Alíquota Cofins': campos[13],
            'Qtde Alíquota Cofins': '',
            'Vlr Cofins': campos[14],
            'Conta Contábil': campos[17],
            'Débito/Crédito': '',
        }
    except IndexError:
        print(f"Linha F100 inválida: {line}")
        return None


if __name__ == '__main__':
    main()
