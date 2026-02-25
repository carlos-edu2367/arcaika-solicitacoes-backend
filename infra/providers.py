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
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, HRFlowable
        )
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfbase import pdfmetrics

        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        elements = []
        styles = getSampleStyleSheet()

        # 🎨 Paleta moderna
        COR_LARANJA = colors.HexColor("#F97316")
        COR_PRETO = colors.HexColor("#111827")
        COR_CINZA_TEXTO = colors.HexColor("#374151")
        COR_CINZA_SUAVE = colors.HexColor("#F3F4F6")
        COR_DIVISOR = colors.HexColor("#E5E7EB")
        COR_BRANCA = colors.white

        # =========================
        # ESTILOS
        # =========================

        style_header = ParagraphStyle(
            'HeaderTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=COR_BRANCA,
            fontName="Helvetica-Bold",
            spaceAfter=0
        )

        style_os = ParagraphStyle(
            'OSNumber',
            parent=styles['Normal'],
            fontSize=14,
            textColor=COR_BRANCA,
            alignment=TA_RIGHT,
            fontName="Helvetica-Bold"
        )

        style_section_title = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=COR_PRETO,
            fontName="Helvetica-Bold",
            spaceAfter=8,
            spaceBefore=15
        )

        style_label = ParagraphStyle(
            'LabelStyle',
            parent=styles['Normal'],
            fontSize=8,
            textColor=COR_CINZA_TEXTO,
            fontName="Helvetica-Bold"
        )

        style_value = ParagraphStyle(
            'ValueStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=COR_PRETO,
            leading=14
        )

        # =========================
        # HEADER PREMIUM
        # =========================

        os_text = str(solicitacao.ordem_servico)
        if not os_text.upper().startswith("OS"):
            os_text = f"OS-{os_text}"

        header_table = Table(
            [[
                Paragraph("ORDEM DE SERVIÇO", style_header),
                Paragraph(os_text, style_os)
            ]],
            colWidths=[260, 255]
        )

        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COR_LARANJA),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ('TOPPADDING', (0, 0), (-1, -1), 18),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 18),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(header_table)
        elements.append(Spacer(1, 25))

        # =========================
        # FUNÇÃO PARA CRIAR "CARDS"
        # =========================

        def criar_secao(titulo, campos):

            elements.append(Paragraph(titulo, style_section_title))
            elements.append(HRFlowable(
                width="100%",
                thickness=1,
                color=COR_DIVISOR,
                spaceBefore=2,
                spaceAfter=10
            ))

            dados_formatados = []

            for label, valor in campos:
                dados_formatados.append([
                    Paragraph(label.upper(), style_label),
                    Paragraph(str(valor), style_value)
                ])

            tabela = Table(dados_formatados, colWidths=[120, 395])

            tabela.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), COR_BRANCA),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, COR_DIVISOR),
                ('BOX', (0, 0), (-1, -1), 0.5, COR_DIVISOR),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))

            elements.append(tabela)
            elements.append(Spacer(1, 15))

        # =========================
        # SEÇÃO 1
        # =========================

        criar_secao("Detalhes da Solicitação", [
            ("Assunto", solicitacao.assunto),
            ("Prioridade", solicitacao.prioridade),
            ("Status Atual", solicitacao.status),
            ("Descrição", solicitacao.descricao),
            ("Informações Adicionais", solicitacao.informacoes_adicionais or "-")
        ])

        # =========================
        # SEÇÃO 2
        # =========================

        criar_secao("Dados do Solicitante", [
            ("Nome", solicitacao.nome),
            ("E-mail", solicitacao.email),
            ("Telefone", solicitacao.telefone),
        ])

        # =========================
        # SEÇÃO 3
        # =========================

        local_nome = getattr(solicitacao.local, 'nome', 'N/A')
        unidade_nome = getattr(solicitacao, 'nome_da_unidade', 'N/A')
        local_cidade = getattr(solicitacao.local, 'cidade', '')
        local_estado = getattr(solicitacao.local, 'estado', '')
        cidade_estado = f"{local_cidade}/{local_estado}".strip("/")

        criar_secao("Localização", [
            ("Secretaria", local_nome),
            ("Unidade", unidade_nome),
            ("Cidade/UF", cidade_estado or "-"),
        ])

        # =========================
        # BUILD
        # =========================

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