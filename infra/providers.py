import io
import json
import logging
import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import List, Tuple
from urllib.parse import urlparse
from uuid import UUID
from logging import getLogger             

# 2. Third-Party Libraries (Instalados via pip)
import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from storage3.exceptions import StorageApiError

# ReportLab para geração do PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# 3. Local Application Imports
from application.providers.hash import HashProvider
from domain.entities.solicitacao import Solicitacao
from infra.config import Settings
from supabase import AsyncClient, create_async_client

load_dotenv()

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = "mg.neectify.com"
MAILGUN_BASE_URL = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}"

logger = getLogger(__name__)

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

class INFRAHashProvider(HashProvider):
    def hash(self, text: str) -> str:
        return pwd_context.hash(text)

    def verify(self, hashed: str, text: str) -> bool:
        return pwd_context.verify(text, hashed)

class StorageProvider():
    async def get_by_path(self, path: str, bucket: str = "docs") -> str | None:
        supabase: AsyncClient = await create_async_client(Settings.SUPABASE_URL, Settings.SUPABASE_KEY)
        validade_segundos = 3600
        try:
            resposta = await supabase.storage.from_(bucket).create_signed_url(
                path,
                validade_segundos
            )
        except (StorageApiError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            logger.warning(f"[gerar_url_assinada] Falha ao gerar URL assinada para '{path}': {e}")
            return None
        except Exception as e:
            logger.error(f"[gerar_url_assinada] Erro inesperado para '{path}': {e}", exc_info=True)
            return None

        if isinstance(resposta, dict):
            if "signedURL" in resposta:
                return resposta["signedURL"]
            if "data" in resposta and isinstance(resposta["data"], dict) and "signedURL" in resposta["data"]:
                return resposta["data"]["signedURL"]

        if hasattr(resposta, "get"):
            if resposta.get("signedURL"):
                return resposta.get("signedURL")
            if "data" in resposta and resposta["data"].get("signedURL"):
                return resposta["data"]["signedURL"]

        logger.error(f"[gerar_url_assinada] Resposta inesperada do Supabase: {resposta}")
        return None

    async def upload_file(self, file: UploadFile, bucket: str = "docs") -> str:
        supabase: AsyncClient = await create_async_client(Settings.SUPABASE_URL, Settings.SUPABASE_KEY)
        try:
            file_ext = file.filename.split(".")[-1] if "." in file.filename else ""
            unique_name = f"{uuid.uuid4()}.{file_ext}" if file_ext else str(uuid.uuid4())
            file_path = f"{unique_name}"

            content = await file.read()

            resposta = await supabase.storage.from_(bucket).upload(
                path=file_path,
                file=content,
                file_options={
                    "content-type": file.content_type or "application/octet-stream"
                }
            )

        except (StorageApiError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            logger.warning(f"[upload_file] Falha ao enviar '{file.filename}': {e}")
            raise
        except Exception as e:
            logger.error(f"[upload_file] Erro inesperado no upload: {e}", exc_info=True)
            raise

        if isinstance(resposta, dict):
            if resposta.get("error"):
                logger.error(f"[upload_file] Erro retornado pelo Supabase: {resposta}")
                raise Exception("Erro ao fazer upload do arquivo")

        return file_path

    async def delete_file(self, file_path: str, bucket: str = "docs") -> bool:
        supabase: AsyncClient = await create_async_client(Settings.SUPABASE_URL, Settings.SUPABASE_KEY)
        try:
            resposta = await supabase.storage.from_(bucket).remove([file_path])
        except (StorageApiError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            logger.warning(f"[delete_file] Falha ao deletar '{file_path}': {e}")
            return False
        except Exception as e:
            logger.error(f"[delete_file] Erro inesperado ao deletar '{file_path}': {e}", exc_info=True)
            return False

        if isinstance(resposta, dict) and resposta.get("error"):
            logger.error(f"[delete_file] Supabase retornou erro: {resposta}")
            return False

        return True
    
class Payload(BaseModel):
    id: UUID
    role: str

class TokenProvider():
    def create_token(self, user_id: UUID, role: str) -> str:
        try:
            exp = datetime.now(UTC) + timedelta(days=3)
            payload = {
                "exp": exp,
                "sub": str(user_id),
                "role": role
            }
            return jwt.encode(
                payload,
                Settings.SECRET_KEY,
                algorithm="HS256"
            )
        except JWTError:
            raise HTTPException(
                status_code=401,
                detail="Erro ao gerar token de autenticação"
            )

    def get_payload(self, token: str) -> Payload:
        try:
            decoded = jwt.decode(
                token,
                Settings.SECRET_KEY,
                algorithms=["HS256"]
            )
            return Payload(
                id=UUID(decoded.get("sub")),
                role=str(decoded.get("role"))
            )
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token expirado"
            )
        except JWTError:
            raise HTTPException(
                status_code=401,
                detail="Token inválido"
            )
        
class EmailProvider:

    def inject_neectify_footer(self, html: str, brand_name: str = "Neectify", brand_url: str = "https://www.neectify.com") -> str:
        if brand_url in html:
            return html

        footer_html = f"""
        <div style="margin-top:32px; padding-top:16px; border-top:1px solid #e5e7eb; text-align:center;">
            <p style="margin:0; font-size:11px; color:#9ca3af; font-family: Arial, Helvetica, sans-serif;">
                Este sistema foi desenvolvido pela
                <a href="{brand_url}"
                   target="_blank"
                   rel="noopener noreferrer"
                   style="color:#6b7280; text-decoration:none; font-weight:bold;">
                    {brand_name}
                </a>.
                Gostou? Solicite um orçamento!
            </p>
        </div>
        """
        pattern = re.compile(r"</body\s*>", re.IGNORECASE)
        if pattern.search(html):
            return pattern.sub(f"{footer_html}\n</body>", html, count=1)
        return html + footer_html

    def _gerar_pdf_solicitacao(self, solicitacao: Solicitacao) -> bytes:
        import io
        import os
        from datetime import datetime
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, HRFlowable, Image
        )
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from reportlab.lib.utils import ImageReader

        buffer = io.BytesIO()

        # Margens otimizadas para dar largura de 180mm para o conteúdo (A4 = 210x297)
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=15*mm,
            bottomMargin=15*mm
        )

        elements = []
        styles = getSampleStyleSheet()

        # =========================
        # 🎨 Paleta Moderna Frontend
        # =========================
        COR_LARANJA = colors.HexColor("#F97316")
        COR_LARANJA_ESCURO = colors.HexColor("#EA580C")
        COR_PRETO = colors.HexColor("#111827")
        COR_CINZA_ESCURO = colors.HexColor("#374151")
        COR_CINZA_MEDIO = colors.HexColor("#4B5563")
        COR_CINZA_LABEL = colors.HexColor("#6B7280")
        COR_CINZA_CLARO = colors.HexColor("#F9FAFB")
        COR_BORDA = colors.HexColor("#E5E7EB")
        COR_BORDA_CLARA = colors.HexColor("#F3F4F6")
        COR_BRANCA = colors.white

        # =========================
        # ESTILOS
        # =========================
        style_company = ParagraphStyle('Company', parent=styles['Normal'], fontSize=9, textColor=COR_CINZA_MEDIO, alignment=TA_RIGHT, leading=12)
        style_os_title = ParagraphStyle('OSTitle', parent=styles['Normal'], fontSize=16, textColor=COR_BRANCA, fontName="Helvetica-Bold")
        style_os_date = ParagraphStyle('OSDate', parent=styles['Normal'], fontSize=10, textColor=COR_BRANCA, alignment=TA_RIGHT)

        style_card_title = ParagraphStyle('CardTitle', parent=styles['Normal'], fontSize=10, textColor=COR_LARANJA_ESCURO, fontName="Helvetica-Bold", textTransform="uppercase")
        style_label = ParagraphStyle('Label', parent=styles['Normal'], fontSize=8, textColor=COR_CINZA_LABEL, fontName="Helvetica-Bold", textTransform="uppercase", spaceBottom=2)
        style_value = ParagraphStyle('Value', parent=styles['Normal'], fontSize=11, textColor=COR_PRETO, fontName="Helvetica-Bold", spaceBottom=8)
        
        style_desc_title = ParagraphStyle('DescTitle', parent=styles['Normal'], fontSize=9, textColor=COR_CINZA_MEDIO, fontName="Helvetica-Bold", textTransform="uppercase", spaceBottom=4)
        style_desc_text = ParagraphStyle('DescText', parent=styles['Normal'], fontSize=10, textColor=COR_CINZA_ESCURO, leading=14)
        
        style_footer = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor("#9CA3AF"), alignment=TA_CENTER, leading=10)

        # Dados da Solicitação
        os_text = str(solicitacao.ordem_servico).zfill(4)
        data_hora_atual = datetime.now()

        local_nome = getattr(solicitacao.local, 'nome', 'Não informado')
        local_cidade = getattr(solicitacao.local, 'cidade', '-')
        local_estado = getattr(solicitacao.local, 'estado', '-')
        unidade_nome = getattr(solicitacao, 'nome_da_unidade', 'NÃO INFORMADO')
        if not unidade_nome: unidade_nome = 'NÃO INFORMADO'

        # =========================
        # 1. CABEÇALHO (LOGO E INFO)
        # =========================
        logo_path = os.path.join(os.getcwd(), 'assets', 'logo.png')
        if os.path.exists(logo_path):
            try:
                img_reader = ImageReader(logo_path)
                iw, ih = img_reader.getSize()
                aspect = ih / float(iw)
                target_width = 50 * mm
                target_height = target_width * aspect
                if target_height > 20 * mm:  # Limitando altura máxima
                    target_height = 20 * mm
                    target_width = target_height / aspect

                logo = Image(logo_path, width=target_width, height=target_height)
                logo.hAlign = 'LEFT'
            except Exception:
                logo = Paragraph("<b>ARCAIKA ENGENHARIA</b>", style_value)
        else:
            logo = Paragraph("<b>ARCAIKA ENGENHARIA</b>", style_value)

        company_info = """<font color="#111827"><b>ARCAIKA ENGENHARIA LTDA</b></font><br/>
        CNPJ: 42.907.720/0001-85<br/>
        Al. Botafogo, 174 - Qd 77, L 11 - St. Central<br/>
        Goiânia - GO, 74030-020<br/>
        Tel: (62) 99616-4188"""

        header_table = Table([[logo, Paragraph(company_info, style_company)]], colWidths=[90*mm, 90*mm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(header_table)
        elements.append(HRFlowable(width="100%", thickness=2, color=COR_LARANJA, spaceBefore=0, spaceAfter=15))

        # =========================
        # 2. TÍTULO ORDEM DE SERVIÇO
        # =========================
        title_table = Table([[
            Paragraph(f"ORDEM DE SERVIÇO #{os_text}", style_os_title),
            Paragraph(f"<b>Data:</b> {data_hora_atual.strftime('%d/%m/%Y')}", style_os_date)
        ]], colWidths=[120*mm, 60*mm])
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COR_LARANJA),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 15),
            ('RIGHTPADDING', (1, 0), (1, 0), 15),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 15))

        # =========================
        # 3. SEÇÃO 1 E 2 (LADO A LADO)
        # =========================
        
        # Bloco Esquerdo (Local)
        local_elements = [
            Paragraph("LOCAL", style_card_title),
            HRFlowable(width="100%", thickness=1, color=COR_BORDA, spaceBefore=4, spaceAfter=8),
            Paragraph("SECRETARIA", style_label),
            Paragraph(str(local_nome).upper(), style_value),
            Paragraph("CIDADE / UF", style_label),
            Paragraph(f"{str(local_cidade).upper()} - {str(local_estado).upper()}", style_value),
            Paragraph("UNIDADE / SETOR", style_label),
            Paragraph(str(unidade_nome).upper(), style_value),
        ]
        
        # Bloco Direito (Solicitante)
        solicitante_elements = [
            Paragraph("SOLICITANTE", style_card_title),
            HRFlowable(width="100%", thickness=1, color=COR_BORDA, spaceBefore=4, spaceAfter=8),
            Paragraph("NOME COMPLETO", style_label),
            Paragraph(str(solicitacao.nome).upper(), style_value),
            Paragraph("E-MAIL", style_label),
            Paragraph(str(solicitacao.email), style_value),
            Paragraph("TELEFONE", style_label),
            Paragraph(str(solicitacao.telefone), style_value),
        ]

        card_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COR_CINZA_CLARO),
            ('BOX', (0, 0), (-1, -1), 1, COR_BORDA),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ])

        card_local = Table([[local_elements]], colWidths=[88*mm])
        card_local.setStyle(card_style)

        card_solicitante = Table([[solicitante_elements]], colWidths=[88*mm])
        card_solicitante.setStyle(card_style)

        cards_table = Table([[card_local, '', card_solicitante]], colWidths=[88*mm, 4*mm, 88*mm])
        cards_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(cards_table)
        elements.append(Spacer(1, 15))

        # =========================
        # 4. SEÇÃO 3 (DETALHES DA SOLICITAÇÃO)
        # =========================
        
        # Trata as cores da Prioridade
        pri_text = str(solicitacao.prioridade).upper()
        if pri_text == 'ALTA':
            cor_pri_text = colors.HexColor("#DC2626")
            cor_pri_bg = colors.HexColor("#FEF2F2")
        elif pri_text in ['MÉDIA', 'MEDIA']:
            cor_pri_text = colors.HexColor("#D97706")
            cor_pri_bg = colors.HexColor("#FFFBEB")
        else:
            cor_pri_text = colors.HexColor("#16A34A")
            cor_pri_bg = colors.HexColor("#F0FDF4")
            
        style_pri = ParagraphStyle('Pri', parent=styles['Normal'], fontSize=10, textColor=cor_pri_text, fontName="Helvetica-Bold", alignment=TA_CENTER)
        
        prioridade_t = Table([[Paragraph(pri_text, style_pri)]], colWidths=[35*mm])
        prioridade_t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), cor_pri_bg),
            ('BOX', (0, 0), (-1, -1), 1, cor_pri_text),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))

        assunto_prioridade = Table([[
            [Paragraph("ASSUNTO", style_label), Paragraph(str(solicitacao.assunto).upper(), style_value)],
            [Paragraph("PRIORIDADE", ParagraphStyle('PriL', parent=style_label, alignment=TA_RIGHT)), prioridade_t]
        ]], colWidths=[110*mm, 40*mm])
        assunto_prioridade.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))

        # Container da Descrição
        desc_texto = str(solicitacao.descricao).replace('\n', '<br/>')
        desc_t = Table([[Paragraph(desc_texto, style_desc_text)]], colWidths=[150*mm])
        desc_t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COR_CINZA_CLARO),
            ('BOX', (0, 0), (-1, -1), 1, COR_BORDA_CLARA),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))

        detalhes_elements = [
            Paragraph("DETALHES DA SOLICITAÇÃO", style_card_title),
            HRFlowable(width="100%", thickness=2, color=COR_BORDA_CLARA, spaceBefore=6, spaceAfter=10),
            assunto_prioridade,
            Spacer(1, 10),
            Paragraph("DESCRIÇÃO DO PROBLEMA / SERVIÇO", style_desc_title),
            HRFlowable(width="100%", thickness=1, color=COR_BORDA_CLARA, spaceBefore=2, spaceAfter=6),
            desc_t,
        ]

        # Container opcional de Informações Adicionais (Amarelo)
        if solicitacao.informacoes_adicionais:
            info_texto = str(solicitacao.informacoes_adicionais).replace('\n', '<br/>')
            info_t = Table([[Paragraph(info_texto, style_desc_text)]], colWidths=[150*mm])
            info_t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FFFBEB")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#FEF3C7")),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            detalhes_elements.append(Spacer(1, 15))
            detalhes_elements.append(Paragraph("INFORMAÇÕES ADICIONAIS", style_desc_title))
            detalhes_elements.append(HRFlowable(width="100%", thickness=1, color=COR_BORDA_CLARA, spaceBefore=2, spaceAfter=6))
            detalhes_elements.append(info_t)

        detalhes_card = Table([[detalhes_elements]], colWidths=[180*mm])
        detalhes_card.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COR_BRANCA),
            ('BOX', (0, 0), (-1, -1), 1, COR_BORDA),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(detalhes_card)
        elements.append(Spacer(1, 25))

        # =========================
        # 5. RODAPÉ
        # =========================
        elements.append(HRFlowable(width="100%", thickness=1, color=COR_BORDA, spaceBefore=0, spaceAfter=10))
        elements.append(Paragraph(
            f"Documento gerado eletronicamente pelo Sistema de Solicitações Arcaika Engenharia.<br/>"
            f"Gerado em {data_hora_atual.strftime('%d/%m/%Y')} às {data_hora_atual.strftime('%H:%M:%S')}.",
            style_footer
        ))

        # Build do PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    async def send_email(
        self,
        to: List[str] | str,
        subject: str,
        html: str,
        sender: str = "Neectify <no-reply@mg.neectify.com>",
        cc: List[str] | None = None,
        bcc: List[str] | None = None,
        attachments: List[Tuple[str, bytes, str]] | None = None,
        include_footer: bool = True
    ) -> dict:
        logger.info("Iniciando processo de envio de e-mail")

        if not to:
            raise ValueError("Destinatário não pode ser vazio")

        html_full = self.inject_neectify_footer(html) if include_footer else html
        to_field = ", ".join(to) if isinstance(to, list) else to

        data = {
            "from": sender,
            "to": to_field,
            "subject": subject,
            "html": html_full,
        }

        if cc:
            data["cc"] = ", ".join(cc)
        if bcc:
            data["bcc"] = ", ".join(bcc)

        files = None
        if attachments:
            files = [
                ("attachment", (filename, content, content_type))
                for filename, content, content_type in attachments
            ]

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{MAILGUN_BASE_URL}/messages",
                    auth=("api", MAILGUN_API_KEY),
                    data=data,
                    files=files
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"[EmailProvider] Falha ao enviar email: {e}")
            raise
        logger.info("E-mail enviado!")
        return response.json()
    
    async def aviso_model(
        self,
        admins: list[tuple[str, str]],
        solicitacao: Solicitacao
    ) -> dict:

        if not admins:
            raise ValueError("Lista de admins não pode ser vazia")

        primary_name, primary_email = admins[0]
        cc_emails = [email for _, email in admins[1:]] if len(admins) > 1 else None

        # Garante formatação da OS
        os_text = str(solicitacao.ordem_servico) if str(solicitacao.ordem_servico).upper().startswith("OS") else f"OS-{solicitacao.ordem_servico}"

        # Badge de prioridade
        prioridade_cor = {
            "BAIXA": "#10B981",
            "MEDIA": "#F59E0B",
            "ALTA": "#EF4444"
        }.get(solicitacao.prioridade, "#F97316")

        # Dados da localização
        secretaria = getattr(solicitacao.local, 'nome', '')
        unidade = getattr(solicitacao, 'nome_da_unidade', '')

        # HTML Resumido
        html = f"""
        <html>
        <body style="margin:0;padding:0;background-color:#f3f4f6;font-family:Arial,Helvetica,sans-serif;">
            <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0;">
                <tr>
                    <td align="center">
                        <table width="600" cellpadding="0" cellspacing="0" 
                            style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 10px 25px rgba(0,0,0,0.05);">

                            <!-- Header -->
                            <tr>
                                <td style="background:linear-gradient(90deg,#f97316,#fb923c);padding:24px;text-align:center;">
                                    <h1 style="margin:0;color:#ffffff;font-size:20px;">
                                        Nova Solicitação: {os_text}
                                    </h1>
                                </td>
                            </tr>

                            <!-- Conteúdo -->
                            <tr>
                                <td style="padding:32px;">
                                    <p style="font-size:16px;color:#111827;margin-top:0;">
                                        Olá <strong>{primary_name}</strong>,
                                    </p>

                                    <p style="font-size:14px;color:#4b5563;">
                                        A Ordem de Serviço <strong>{os_text}</strong> acaba de ser registrada no sistema.
                                    </p>

                                    <!-- Card interno Resumido -->
                                    <table width="100%" cellpadding="0" cellspacing="0"
                                        style="margin-top:20px;border:1px solid #e5e7eb;border-radius:8px;">
                                        <tr>
                                            <td style="padding:16px;font-size:14px;color:#374151;">
                                                <p style="margin: 0 0 5px 0;"><strong>Secretaria:</strong> {secretaria}</p>
                                                <p style="margin: 0 0 10px 0;"><strong>Unidade:</strong> {unidade}</p>
                                                <p style="margin: 0 0 10px 0;"><strong>Assunto:</strong> {solicitacao.assunto}</p>
                                                <p style="margin: 0;">
                                                    <strong>Prioridade:</strong>
                                                    <span style="
                                                        background:{prioridade_cor};
                                                        color:#ffffff;
                                                        padding:4px 10px;
                                                        border-radius:999px;
                                                        font-size:12px;
                                                        font-weight:bold;
                                                        margin-left:5px;">
                                                        {solicitacao.prioridade}
                                                    </span>
                                                </p>
                                            </td>
                                        </tr>
                                    </table>

                                    <!-- Aviso do Anexo -->
                                    <div style="background-color: #f9fafb; border-left: 4px solid #f97316; padding: 16px; margin-top: 24px; border-radius: 4px;">
                                        <p style="margin: 0; font-size: 14px; color: #4b5563;">
                                            📄 <strong>Nota:</strong> Todos os detalhes, descrições e informações do cliente estão no <strong>PDF em anexo</strong>.
                                        </p>
                                    </div>

                                    <!-- Botão -->
                                    <div style="text-align:center;margin-top:30px;">
                                        <a href="https://requests.arcaikaengenharia.com"
                                        style="
                                                background:#111827;
                                                color:#ffffff;
                                                padding:12px 24px;
                                                border-radius:8px;
                                                text-decoration:none;
                                                font-weight:bold;
                                                display:inline-block;
                                                font-size:14px;">
                                            Acessar Sistema
                                        </a>
                                    </div>

                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        # Gera o PDF em memória
        pdf_content = self._gerar_pdf_solicitacao(solicitacao)
        pdf_filename = f"Solicitacao_{os_text}.pdf"

        # Usa o nome da unidade se disponível, senão a secretaria no assunto
        local_assunto = unidade if unidade else secretaria

        return await self.send_email(
            to=primary_email,
            subject=f"🔥 Nova solicitação: {os_text} - {local_assunto}",
            html=html,
            cc=cc_emails,
            attachments=[(pdf_filename, pdf_content, "application/pdf")],
            include_footer=True
        )