from fpdf import FPDF
import io
from datetime import datetime
from utils.logging_config import get_logger

logger = get_logger(__name__)

class StudentContractPDF(FPDF):
    def header(self):
        try:
            self.image('logo-amicando-RGB.jpg', x=10, y=10, w=30)
        except Exception:
            pass
        self.set_y(15)
        self.set_x(45)
        self.set_font('Helvetica', '', 10)
        self.cell(0, 5, 'Neli Ceriotti Nishitani Egami ME CNPJ 35.159.314/0001-16', 0, 1, 'L')
        self.set_x(45)
        self.cell(0, 5, 'Rua Alagoas nº 45, Sala 103 - Bairro Humaitá Bento Gonçalves / RS', 0, 1, 'L')
        self.set_x(45)
        self.cell(0, 5, 'Tel: 54-999121787 - amicando.atelier@gmail.com', 0, 1, 'L')
        
        self.set_y(40)
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'Contrato de Prestação de Serviços de Aulas de Cerâmica', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def pt_date(date_str_or_obj):
    if not date_str_or_obj:
        return "___/___/______"
    try:
        if isinstance(date_str_or_obj, str):
            dt = datetime.strptime(date_str_or_obj, '%Y-%m-%d')
        else:
            dt = date_str_or_obj
        
        data_atual = dt.strftime("%d de %B de %Y")
        months = {
            'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março', 'April': 'Abril',
            'May': 'Maio', 'June': 'Junho', 'July': 'Julho', 'August': 'Agosto',
            'September': 'Setembro', 'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'
        }
        for eng, pt in months.items():
            data_atual = data_atual.replace(eng, pt)
        return data_atual
    except:
        return str(date_str_or_obj)

def numero_por_extenso(valor):
    try:
        if valor == 0: return "zero"
        
        unidades = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove"]
        dezenas_10 = ["dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
        dezenas = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
        centenas = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos"]
        
        reais = int(valor)
        centavos = int(round((valor - reais) * 100))
        
        def converte_ate_999(n):
            if n == 100: return "cem"
            elif n == 0: return ""
            c = n // 100
            d = (n % 100) // 10
            u = n % 10
            
            partes = []
            if c > 0: partes.append(centenas[c])
            if d == 1:
                partes.append(dezenas_10[u])
            else:
                if d > 1: partes.append(dezenas[d])
                if u > 0: partes.append(unidades[u])
            return " e ".join(partes)

        if reais == 0:
            res_reais = ""
        elif reais == 1:
            res_reais = "um real"
        elif reais < 1000:
            res_reais = f"{converte_ate_999(reais)} reais"
        else:
            mil = reais // 1000
            resto = reais % 1000
            str_mil = "um mil" if mil == 1 else f"{converte_ate_999(mil)} mil"
            res_reais = str_mil
            if resto > 0:
                if resto <= 100 or resto % 100 == 0:
                    res_reais += f" e {converte_ate_999(resto)}"
                else:
                    res_reais += f", {converte_ate_999(resto)}"
            res_reais += " reais"
            
        if centavos == 0:
            return res_reais
        elif centavos == 1:
            res_centavos = "um centavo"
        else:
            res_centavos = f"{converte_ate_999(centavos)} centavos"
            
        if not res_reais:
            return res_centavos
        return f"{res_reais} e {res_centavos}"
    except:
        return ""

def generate_student_contract_pdf(student_data):
    """
    Generates a personalized PDF contract for a student.
    student_data: dict with name, cpf, rg, endereco, phone, email, weekday_name, start_time, end_time, price_per_class, join_date
    """
    # Use HTML support for FPDF to easily allow bold inline text in a justified paragraph.
    from fpdf import HTMLMixin
    
    class MyFPDF(StudentContractPDF, HTMLMixin):
        pass
        
    pdf = MyFPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', '', 11)
    
    # Fallback for missing data
    def fb(val):
        return val if val and str(val).strip() != "" else "___________"

    # Preâmbulo
    preambulo = (
        f"<p align=\"justify\">Pelo presente instrumento particular, de um lado, Neli Ceriotti Nishitani Egami ME, pessoa jurídica de "
        f"direito privado, inscrita no CNPJ sob o nº 35.159.314/0001-16, com sede na Rua Alagoas, nº 45, Sala 103, "
        f"Bairro Humaitá, Bento Gonçalves/RS, doravante denominada CONTRATADA (Prestadora de Serviços), e de "
        f"outro lado, a CONTRATANTE (Aluna/Cliente), {fb(student_data.get('name'))}, portadora da Carteira de "
        f"Identidade nº {fb(student_data.get('rg'))} e do CPF nº {fb(student_data.get('cpf'))}, residente e "
        f"domiciliada na {fb(student_data.get('endereco'))}, e-mail {fb(student_data.get('email'))} e telefone "
        f"{fb(student_data.get('phone'))}, doravante denominada CONTRATANTE. As Partes, de comum e recíproco acordo, "
        f"celebram o presente Contrato de Prestação de Serviços, regido pelas cláusulas e condições a seguir expostas.</p>"
    )
    pdf.write_html(preambulo)
    pdf.ln(5)

    def print_clause(num, html_text):
        pdf.write_html(f"<p align=\"justify\"><b>CLÁUSULA {num}ª</b> - {html_text}</p>")
        pdf.ln(5)

    # CLÁUSULA 1ª
    c1_txt = "O presente contrato tem como objeto a prestação de serviços de aulas de cerâmica (o \"Serviço\"), a serem realizadas pela CONTRATADA em favor da CONTRATANTE, visando o aprendizado prático e teórico da arte cerâmica."
    print_clause(1, c1_txt)

    # CLÁUSULA 2ª
    join_date_pt = pt_date(student_data.get('join_date'))
    c2_txt = (f"Os serviços a serem prestados consistem na oferta de aulas práticas e teóricas de cerâmica, com as seguintes especificações: "
              f"<b>Duração Semanal:</b> 2 (duas) horas; "
              f"<b>Frequência:</b> Semanal; "
              f"<b>Local das Aulas:</b> Rua Alagoas, nº 45, Sala 103, Bairro Humaitá, Bento Gonçalves/RS; "
              f"<b>Dia e Horário:</b> {fb(student_data.get('weekday_name'))}, das {fb(student_data.get('start_time'))} às {fb(student_data.get('end_time'))}; "
              f"<b>Início das Aulas:</b> {join_date_pt}. Os materiais (argila e esmaltes) bem como as queimas serão cobrados à parte, conforme tabela de preços vigente no ateliê.")
    print_clause(2, c2_txt)

    # CLÁUSULA 3ª
    c3_txt = "Peças danificadas durante o processo de secagem ou queima (rachaduras, estouros, falhas de esmalte) são riscos inerentes à cerâmica, não cabendo ao CONTRATADO(A) responsabilidade por refação."
    print_clause(3, c3_txt)

    # CLÁUSULA 4ª
    valor = float(student_data.get('price_per_class', 95.00))
    val_str = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    val_extenso = numero_por_extenso(valor)
    
    c4_txt = f"A CONTRATANTE pagará à CONTRATADA o valor de R$ {val_str} ({val_extenso}) por aula semanal, referente à prestação dos serviços descritos na Cláusula 2. O valor mensal será o resultado da multiplicação do valor da aula pelo número de aulas semanais efetivamente ministradas no mês (4 ou 5 aulas, dependendo do calendário). O pagamento deverá ser efetuado até o dia 10 de cada mês. O primeiro pagamento será realizado na data de assinatura deste contrato. Este valor será reajustado anualmente, tendo como referência o IPCA."
    print_clause(4, c4_txt)

    # CLÁUSULA 5ª
    c5_txt = "A CONTRATADA se obriga a ministrar as aulas conforme o objeto deste contrato, mantendo a qualidade de ensino e o cronograma estabelecido. Em caso de eventual falta ou impossibilidade de ministrar a aula, a CONTRATADA deverá comunicar a CONTRATANTE com antecedência mínima de 24 horas, devendo a aula ser reposta em data e horário a serem mutuamente acordados. A aula deverá ser reposta no prazo máximo de 30 (trinta) dias a contar da data da falta."
    print_clause(5, c5_txt)

    # CLÁUSULA 6ª
    c6_txt = "A CONTRATANTE se obriga a efetuar o pagamento do valor acordado nas datas e condições estabelecidas na Cláusula 4 e a frequentar as aulas no dia e horário definidos. A CONTRATANTE deverá comunicar a CONTRATADA com antecedência mínima de 24 horas sobre qualquer eventual falta. No caso de ausência sem prévia comunicação, será considerado como aula realizada não gerando direito à reposição da aula."
    print_clause(6, c6_txt)

    # CLÁUSULA 7ª
    c7_txt = f"O presente contrato é por prazo indeterminado, iniciando-se em {join_date_pt}."
    print_clause(7, c7_txt)

    # CLÁUSULA 8ª
    c8_txt = "Qualquer uma das partes poderá rescindir o presente contrato, a qualquer tempo, mediante aviso prévio de 30 dias, por escrito. A rescisão por justa causa, como o descumprimento de qualquer cláusula contratual, poderá ocorrer imediatamente, sem a necessidade de aviso prévio."
    print_clause(8, c8_txt)

    # CLÁUSULA 9ª
    c9_txt = "Fica eleito o foro da Comarca de Bento Gonçalves/RS para dirimir quaisquer dúvidas oriundas deste contrato, renunciando a qualquer outro, por mais privilegiado que seja."
    print_clause(9, c9_txt)

    # CLÁUSULA 10ª
    c10_txt = "A CONTRATANTE autoriza, de forma gratuita e por prazo indeterminado, que a CONTRATADA utilize sua imagem e/ou fotografias e vídeos de suas peças cerâmicas produzidas durante as aulas para fins de: Divulgação em redes sociais (Instagram, Facebook, site oficial, etc.); Materiais promocionais e informativos do ateliê Amicando.<br><br><b>Parágrafo Único:</b> A presente autorização não cria qualquer vínculo trabalhista ou obrigação de pagamento de cachê/royalties, sendo firmada em caráter de colaboração para a divulgação da arte cerâmica."
    print_clause(10, c10_txt)

    # Conclusion
    pdf.write_html("<p align=\"justify\">E por estarem justos e contratados, assinam o presente em 2 (duas) vias de igual teor e forma, na presença das testemunhas abaixo.</p>")
    pdf.ln(10)

    data_atual = pt_date(datetime.now())
        
    pdf.cell(0, 10, f"Bento Gonçalves/RS, {data_atual}.", 0, 1, 'L')
    pdf.ln(30)

    # Signature lines
    y_sig = pdf.get_y()
    pdf.line(20, y_sig, 90, y_sig)
    pdf.line(110, y_sig, 180, y_sig)
    pdf.set_y(y_sig + 2)
    pdf.set_x(20)
    pdf.cell(70, 6, "Contratante", 0, 0, 'C')
    pdf.set_x(110)
    pdf.cell(70, 6, "Contratada", 0, 1, 'C')

    return io.BytesIO(pdf.output(dest='S'))
