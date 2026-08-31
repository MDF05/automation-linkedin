"""
Content Generator Service — Pembuatan Konten LinkedIn dengan AI.

Komponen ini menyediakan:
- ``ContentGenerator`` — class utama untuk menghasilkan variasi konten LinkedIn
  - ``generate_content()``  — hasilkan 3 variasi konten (Requirements 2.2, 2.3, 2.4, 2.9, 2.11)
  - ``split_thread()``      — pecah konten panjang menjadi bagian-bagian thread
  - ``generate_promo()``    — hasilkan 3 variasi copywriting promosi (Requirements 3.1, 3.2, 3.3)

Alur utama (sesuai flowchart Module A di design.md):
  1. search_service.search_references(topic) — kumpulkan referensi
  2. ai_service.generate(prompt + references) × 3 — hasilkan 3 variasi
  3. Validasi thread: split jika content_type='thread' atau len > 3.000

Requirements: 2.2, 2.3, 2.4, 2.9, 2.11, 3.1, 3.2, 3.3
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.services.ai_service import AIRequest, AllProvidersExhaustedError, ProviderChain
from app.services.search_service import SearchResult, search_references

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Batas karakter per bagian thread sesuai LinkedIn (Requirements 2.11)
_THREAD_MAX_CHARS = 3_000

# Maksimum bagian thread (Requirements 2.11)
_THREAD_MAX_PARTS = 10

# Target panjang konten per pilihan ContentLength
_LENGTH_TARGET: Dict[str, int] = {
    "pendek": 300,
    "sedang": 1_000,
    "panjang": 2_500,
}

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ContentVariant = Dict[str, Any]
"""
Satu variasi konten hasil generate.

Keys:
    content (str):    Teks konten LinkedIn.
    char_count (int): Jumlah karakter.
    hashtags (list):  Daftar hashtag yang diekstrak dari konten.
    is_thread (bool): True jika konten sudah dipecah jadi thread.
    thread_parts (list | None): List dict {part_number, content, char_count} jika thread.
"""

PromoVariant = Dict[str, Any]
"""
Satu variasi copywriting promosi.

Keys:
    headline (str):  Headline yang menarik.
    body (str):      Body post dengan value proposition.
    cta (str):       Call-to-action.
    hashtags (list): 5–10 hashtag relevan.
    full_content (str): headline + body + cta + hashtags dalam satu string.
    char_count (int): Jumlah karakter full_content.
"""


# ---------------------------------------------------------------------------
# Helpers (module-level, dapat ditest terpisah)
# ---------------------------------------------------------------------------


def _extract_hashtags(text: str) -> List[str]:
    """
    Ekstrak semua hashtag dari teks.

    Args:
        text: Teks konten LinkedIn.

    Returns:
        List hashtag unik (termasuk tanda '#'), misalnya ['#karir', '#tips'].
    """
    return list(dict.fromkeys(re.findall(r"#\w+", text)))


def _build_references_block(references: List[SearchResult]) -> str:
    """
    Buat blok teks ringkasan referensi untuk disertakan dalam prompt AI.

    Args:
        references: List SearchResult dari search_service.

    Returns:
        String multi-baris berisi ringkasan referensi, atau string kosong jika tidak ada.
    """
    if not references:
        return ""

    lines = ["Referensi terkini yang relevan:"]
    for i, ref in enumerate(references[:5], start=1):
        title = ref.get("title", "").strip()
        snippet = ref.get("snippet", "").strip()
        url = ref.get("url", "").strip()
        parts = [f"{i}. {title}"]
        if snippet:
            parts.append(f"   {snippet[:200]}")
        if url:
            parts.append(f"   Sumber: {url}")
        lines.append("\n".join(parts))

    return "\n\n".join(lines)


def _build_content_prompt(
    topic: str,
    description: Optional[str],
    content_type: str,
    tone: str,
    length: str,
    references_block: str,
    variation_index: int,
) -> str:
    """
    Bangun prompt untuk generate satu variasi konten LinkedIn.

    Args:
        topic:           Topik atau judul konten.
        description:     Deskripsi ide tambahan (opsional).
        content_type:    Tipe konten (storytelling, tips_list, dll).
        tone:            Tone tulisan (profesional, kasual, inspiratif, edukasi).
        length:          Panjang konten (pendek, sedang, panjang).
        references_block: Blok teks referensi dari search_service.
        variation_index: Indeks variasi (1, 2, 3) — mempengaruhi gaya penulisan.

    Returns:
        String prompt yang siap dikirim ke AI provider.
    """
    target_chars = _LENGTH_TARGET.get(length, 1_000)

    # Instruksi gaya penulisan berbeda per variasi (Requirements 2.4)
    variation_hints = {
        1: "Mulai dengan pernyataan kuat atau fakta mengejutkan.",
        2: "Mulai dengan pertanyaan retorika atau skenario relatable.",
        3: "Mulai dengan cerita singkat atau analogi yang menarik.",
    }
    variation_hint = variation_hints.get(variation_index, "")

    type_instructions = {
        "storytelling": "Gunakan struktur narasi: situasi → konflik → solusi → pelajaran.",
        "tips_list":    "Format sebagai numbered list atau bullet points dengan penjelasan singkat.",
        "pertanyaan":   "Ajukan pertanyaan provocative yang mengundang diskusi dan komentar.",
        "kutipan":      "Pilih satu kutipan kuat, lalu elaborasi maknanya dengan pengalaman nyata.",
        "video_script": "Format sebagai script: hook (5 detik) → isi (45 detik) → CTA (10 detik).",
        "thread":       "Format sebagai thread: bagian 1/N sebagai hook, lanjutkan dengan numbered parts.",
        "promo":        "Format promosi profesional dengan headline, value proposition, dan CTA.",
    }
    type_instruction = type_instructions.get(content_type, "")

    prompt_parts = [
        f"Buat konten LinkedIn tentang: {topic}",
    ]

    if description:
        prompt_parts.append(f"Konteks tambahan: {description}")

    prompt_parts.extend([
        f"Tipe konten: {content_type}. {type_instruction}",
        f"Tone: {tone}.",
        f"Panjang target: sekitar {target_chars} karakter.",
        variation_hint,
    ])

    if references_block:
        prompt_parts.append(f"\n{references_block}")

    prompt_parts.extend([
        "\nPanduan tambahan:",
        "- Tulis dalam Bahasa Indonesia yang natural dan engaging.",
        "- Sertakan 3–5 hashtag relevan di akhir konten.",
        "- Jangan gunakan emoji berlebihan.",
        "- Langsung mulai konten tanpa pembukaan seperti 'Berikut adalah...'.",
    ])

    return "\n".join(part for part in prompt_parts if part)


def _build_promo_prompt(
    description: str,
    promo_type: str,
    items: List[str],
    target_audience: str,
    variation_index: int,
) -> str:
    """
    Bangun prompt untuk generate satu variasi copywriting promosi.

    Args:
        description:      Deskripsi jasa/produk yang dipromosikan.
        promo_type:       Tipe promosi (penawaran_spesial/portofolio/testimoni/pengumuman).
        items:            Daftar item atau poin yang ingin ditonjolkan.
        target_audience:  Target audiens promosi.
        variation_index:  Indeks variasi (1, 2, 3).

    Returns:
        String prompt untuk AI provider.
    """
    # Gaya copywriting berbeda per variasi (Requirements 3.3)
    variation_styles = {
        1: "Gunakan gaya direct dan benefit-focused. Tonjolkan hasil nyata.",
        2: "Gunakan gaya storytelling. Ceritakan masalah target audiens lalu tawarkan solusi.",
        3: "Gunakan gaya social proof. Tekankan kepercayaan, testimoni, atau pencapaian.",
    }
    style_hint = variation_styles.get(variation_index, "")

    type_angles = {
        "penawaran_spesial": "Tekankan urgensi, batas waktu, dan nilai penghematan.",
        "portofolio":        "Tonjolkan hasil kerja, keahlian, dan kredibilitas.",
        "testimoni":         "Gunakan kata-kata klien atau hasil terukur sebagai bukti.",
        "pengumuman":        "Sampaikan berita dengan antusias dan jelaskan implikasi positifnya.",
    }
    type_angle = type_angles.get(promo_type, "")

    items_text = "\n".join(f"- {item}" for item in items) if items else "(tidak ada item spesifik)"

    return f"""Buat copywriting promosi LinkedIn untuk:

Deskripsi: {description}
Tipe promosi: {promo_type}. {type_angle}
Target audiens: {target_audience}
Item yang dipromosikan:
{items_text}

Gaya penulisan: {style_hint}

Format output HARUS persis seperti ini (gunakan label yang sama):
HEADLINE: [headline menarik, maksimal 150 karakter]
BODY: [body post dengan value proposition, 200–500 karakter]
CTA: [call-to-action yang jelas dan actionable, maksimal 100 karakter]
HASHTAG: [5–10 hashtag relevan dipisah spasi, contoh: #digitalmarketing #freelance]

Panduan:
- Tulis dalam Bahasa Indonesia yang profesional namun engaging.
- Setiap bagian harus berdiri sendiri namun saling melengkapi.
- Jangan ulangi struktur yang sama dari prompt sebelumnya."""


def _parse_promo_response(raw_content: str, full_fallback: str) -> Dict[str, Any]:
    """
    Parse respons AI untuk format promosi terstruktur.

    Mencoba parse label HEADLINE/BODY/CTA/HASHTAG.
    Jika parsing gagal, gunakan seluruh raw_content sebagai full_content.

    Args:
        raw_content:   Teks mentah dari AI provider.
        full_fallback: Teks fallback jika parsing gagal.

    Returns:
        Dict dengan keys: headline, body, cta, hashtags, full_content, char_count.
    """
    headline = body = cta = ""
    hashtags: List[str] = []

    headline_match = re.search(r"HEADLINE:\s*(.+?)(?=\n(?:BODY|CTA|HASHTAG)|$)", raw_content, re.DOTALL)
    body_match = re.search(r"BODY:\s*(.+?)(?=\n(?:HEADLINE|CTA|HASHTAG)|$)", raw_content, re.DOTALL)
    cta_match = re.search(r"CTA:\s*(.+?)(?=\n(?:HEADLINE|BODY|HASHTAG)|$)", raw_content, re.DOTALL)
    hashtag_match = re.search(r"HASHTAG:\s*(.+?)(?=\n(?:HEADLINE|BODY|CTA)|$)", raw_content, re.DOTALL)

    if headline_match:
        headline = headline_match.group(1).strip()
    if body_match:
        body = body_match.group(1).strip()
    if cta_match:
        cta = cta_match.group(1).strip()
    if hashtag_match:
        raw_hashtags = hashtag_match.group(1).strip()
        hashtags = [h.strip() for h in raw_hashtags.split() if h.startswith("#")]

    # Jika salah satu bagian kosong, fallback ke teks penuh
    if not (headline and body and cta):
        full_content = raw_content.strip() or full_fallback
        hashtags = _extract_hashtags(full_content)
        return {
            "headline": "",
            "body": full_content,
            "cta": "",
            "hashtags": hashtags,
            "full_content": full_content,
            "char_count": len(full_content),
        }

    # Ekstrak hashtag dari body jika tidak ada di blok HASHTAG
    if not hashtags:
        hashtags = _extract_hashtags(f"{body} {cta}")

    full_content = f"{headline}\n\n{body}\n\n{cta}\n\n{' '.join(hashtags)}".strip()

    return {
        "headline": headline,
        "body": body,
        "cta": cta,
        "hashtags": hashtags,
        "full_content": full_content,
        "char_count": len(full_content),
    }


# ---------------------------------------------------------------------------
# ContentGenerator
# ---------------------------------------------------------------------------


class ContentGenerator:
    """
    Layanan untuk menghasilkan konten LinkedIn menggunakan AI dan referensi web.

    Args:
        provider_chain: Instance ``ProviderChain`` dari ai_service yang sudah
                        dikonfigurasi dengan provider dan db session.

    Usage::

        generator = ContentGenerator(provider_chain)
        variants = await generator.generate_content(
            topic="Produktivitas Developer",
            description="Tips bekerja efisien dari rumah",
            content_type="tips_list",
            tone="profesional",
            length="sedang",
        )
        # variants → list of 3 dicts: {content, char_count, hashtags, ...}
    """

    def __init__(self, provider_chain: ProviderChain) -> None:
        self._chain = provider_chain

    # ------------------------------------------------------------------
    # Public API — Module A
    # ------------------------------------------------------------------

    async def generate_content(
        self,
        topic: str,
        description: Optional[str],
        content_type: str,
        tone: str,
        length: str,
    ) -> List[ContentVariant]:
        """
        Hasilkan 3 variasi konten LinkedIn untuk topik yang diberikan.

        Alur:
        1. Panggil search_service.search_references(topic) untuk kumpulkan referensi
           (Requirements 2.2).
        2. Buat 3 prompt dengan gaya penulisan berbeda.
        3. Panggil ai_service.generate() untuk setiap prompt
           (Requirements 2.3, 2.4).
        4. Jika content_type='thread' atau konten > 3.000 karakter,
           split menjadi thread parts (Requirements 2.11).

        Args:
            topic:        Topik atau judul konten.
            description:  Deskripsi ide tambahan (opsional).
            content_type: Tipe konten (storytelling/tips_list/pertanyaan/kutipan/
                          video_script/thread).
            tone:         Tone tulisan (profesional/kasual/inspiratif/edukasi).
            length:       Panjang konten (pendek/sedang/panjang).

        Returns:
            List tepat 3 ``ContentVariant`` dict dengan keys:
            - ``content`` (str)
            - ``char_count`` (int)
            - ``hashtags`` (list[str])
            - ``is_thread`` (bool)
            - ``thread_parts`` (list | None)

        Raises:
            AllProvidersExhaustedError: Jika semua provider AI gagal setelah 3 percobaan
                                        (Requirements 2.9).

        Requirements: 2.2, 2.3, 2.4, 2.9, 2.11
        """
        # Step 1: Kumpulkan referensi via search_service (Requirements 2.2)
        references: List[SearchResult] = []
        try:
            references = await search_references(topic, source="google")
            logger.info(
                "ContentGenerator.generate_content: %d referensi ditemukan untuk '%s'",
                len(references),
                topic,
            )
        except Exception as exc:
            logger.warning(
                "ContentGenerator.generate_content: search_references gagal (%s), lanjut tanpa referensi.",
                exc,
            )

        references_block = _build_references_block(references)

        # Step 2 & 3: Generate 3 variasi dengan prompt berbeda (Requirements 2.3, 2.4)
        variants: List[ContentVariant] = []
        errors: List[str] = []

        for i in range(1, 4):
            prompt = _build_content_prompt(
                topic=topic,
                description=description,
                content_type=content_type,
                tone=tone,
                length=length,
                references_block=references_block,
                variation_index=i,
            )

            request = AIRequest(
                prompt=prompt,
                system_prompt=(
                    "Kamu adalah copywriter LinkedIn berpengalaman yang menulis konten "
                    "dalam Bahasa Indonesia. Hasilkan konten yang authentic, engaging, "
                    "dan sesuai dengan persona profesional LinkedIn."
                ),
                max_tokens=2048,
                temperature=0.7 + (i - 1) * 0.05,  # sedikit variasi temperature
                module="A",
            )

            try:
                response = await self._chain.generate(request)
                raw_content = response.content.strip()

                # Step 4: Validasi thread (Requirements 2.11)
                is_thread = content_type == "thread" or len(raw_content) > _THREAD_MAX_CHARS
                thread_parts: Optional[List[Dict[str, Any]]] = None

                if is_thread:
                    thread_parts = self.split_thread(raw_content)

                hashtags = _extract_hashtags(raw_content)

                variants.append({
                    "content": raw_content,
                    "char_count": len(raw_content),
                    "hashtags": hashtags,
                    "is_thread": is_thread,
                    "thread_parts": thread_parts,
                })

                logger.info(
                    "ContentGenerator.generate_content: variasi %d berhasil (%d chars, provider=%s)",
                    i,
                    len(raw_content),
                    response.provider,
                )

            except AllProvidersExhaustedError:
                # Semua provider gagal — catat dan re-raise setelah semua variasi dicoba
                msg = f"Semua provider AI gagal untuk variasi {i}"
                logger.error("ContentGenerator.generate_content: %s", msg)
                errors.append(msg)
                # Tambahkan placeholder agar loop bisa dilanjutkan;
                # jika semua gagal akan raise di bawah
                variants.append({
                    "content": "",
                    "char_count": 0,
                    "hashtags": [],
                    "is_thread": False,
                    "thread_parts": None,
                    "error": msg,
                })

        # Jika semua 3 variasi gagal, raise error (Requirements 2.9)
        successful = [v for v in variants if v.get("content")]
        if not successful:
            raise AllProvidersExhaustedError(
                message=(
                    "Content generation gagal: semua provider AI tidak dapat digunakan. "
                    f"Detail: {'; '.join(errors)}"
                )
            )

        return variants

    # ------------------------------------------------------------------
    # Public API — Thread Splitting
    # ------------------------------------------------------------------

    def split_thread(
        self,
        content: str,
        max_chars: int = _THREAD_MAX_CHARS,
    ) -> List[Dict[str, Any]]:
        """
        Pecah konten panjang menjadi bagian-bagian thread LinkedIn.

        Strategi pemecahan:
        1. Coba pecah per paragraf (double newline) — pertahankan paragraf utuh.
        2. Jika paragraf terlalu panjang, pecah per kalimat.
        3. Jika masih terlalu panjang, pecah paksa di batas karakter.
        4. Maksimum _THREAD_MAX_PARTS bagian (Requirements 2.11).

        Args:
            content:   Teks konten yang akan dipecah.
            max_chars: Batas karakter per bagian (default 3.000).

        Returns:
            List dict ``{part_number, content, char_count}`` — maksimal 10 item.

        Requirements: 2.11
        """
        if not content or len(content) <= max_chars:
            return [{"part_number": 1, "content": content, "char_count": len(content)}]

        # Pecah per paragraf
        paragraphs = [p.strip() for p in re.split(r"\n\n+", content) if p.strip()]

        parts: List[str] = []
        current_part = ""

        for paragraph in paragraphs:
            # Jika satu paragraf sendiri melebihi max_chars, pecah per kalimat
            if len(paragraph) > max_chars:
                sentences = re.split(r"(?<=[.!?])\s+", paragraph)
                for sentence in sentences:
                    # Jika satu kalimat sendiri melebihi max_chars, pecah paksa
                    if len(sentence) > max_chars:
                        for i in range(0, len(sentence), max_chars):
                            chunk = sentence[i : i + max_chars].strip()
                            if chunk:
                                if current_part:
                                    parts.append(current_part)
                                    current_part = ""
                                parts.append(chunk)
                    else:
                        candidate = (current_part + "\n\n" + sentence).strip() if current_part else sentence
                        if len(candidate) > max_chars:
                            if current_part:
                                parts.append(current_part)
                            current_part = sentence
                        else:
                            current_part = candidate
            else:
                candidate = (current_part + "\n\n" + paragraph).strip() if current_part else paragraph
                if len(candidate) > max_chars:
                    if current_part:
                        parts.append(current_part)
                    current_part = paragraph
                else:
                    current_part = candidate

        if current_part:
            parts.append(current_part)

        # Batasi ke _THREAD_MAX_PARTS bagian
        parts = parts[:_THREAD_MAX_PARTS]

        return [
            {
                "part_number": idx + 1,
                "content": part,
                "char_count": len(part),
            }
            for idx, part in enumerate(parts)
            if part
        ]

    # ------------------------------------------------------------------
    # Public API — Module B
    # ------------------------------------------------------------------

    async def generate_promo(
        self,
        description: str,
        promo_type: str,
        items: List[str],
        target_audience: str,
    ) -> List[PromoVariant]:
        """
        Hasilkan 3 variasi copywriting promosi LinkedIn untuk Module B.

        Setiap variasi memiliki struktur: headline, body, CTA, dan 5–10 hashtag.
        Masing-masing variasi menggunakan gaya copywriting yang berbeda untuk
        menghindari pola posting yang monoton (Requirements 3.3).

        Args:
            description:     Deskripsi jasa/produk yang dipromosikan.
            promo_type:      Tipe promosi (penawaran_spesial/portofolio/
                             testimoni/pengumuman).
            items:           Daftar item atau poin yang ingin ditonjolkan.
            target_audience: Deskripsi target audiens.

        Returns:
            List tepat 3 ``PromoVariant`` dict dengan keys:
            - ``headline`` (str)
            - ``body`` (str)
            - ``cta`` (str)
            - ``hashtags`` (list[str]) — 5–10 hashtag
            - ``full_content`` (str) — konten lengkap siap posting
            - ``char_count`` (int)

        Raises:
            AllProvidersExhaustedError: Jika semua provider AI gagal.

        Requirements: 3.1, 3.2, 3.3
        """
        variants: List[PromoVariant] = []
        errors: List[str] = []

        for i in range(1, 4):
            prompt = _build_promo_prompt(
                description=description,
                promo_type=promo_type,
                items=items,
                target_audience=target_audience,
                variation_index=i,
            )

            request = AIRequest(
                prompt=prompt,
                system_prompt=(
                    "Kamu adalah copywriter LinkedIn berpengalaman yang ahli dalam "
                    "membuat konten promosi profesional. Tulis dalam Bahasa Indonesia "
                    "yang persuasif, jelas, dan sesuai untuk audiens LinkedIn profesional."
                ),
                max_tokens=1024,
                temperature=0.75 + (i - 1) * 0.05,
                module="B",
            )

            try:
                response = await self._chain.generate(request)
                raw_content = response.content.strip()

                variant = _parse_promo_response(raw_content, full_fallback=raw_content)
                variants.append(variant)

                logger.info(
                    "ContentGenerator.generate_promo: variasi %d berhasil (%d chars, provider=%s)",
                    i,
                    variant["char_count"],
                    response.provider,
                )

            except AllProvidersExhaustedError:
                msg = f"Semua provider AI gagal untuk variasi promo {i}"
                logger.error("ContentGenerator.generate_promo: %s", msg)
                errors.append(msg)
                variants.append({
                    "headline": "",
                    "body": "",
                    "cta": "",
                    "hashtags": [],
                    "full_content": "",
                    "char_count": 0,
                    "error": msg,
                })

        # Jika semua 3 variasi gagal, raise error
        successful = [v for v in variants if v.get("full_content")]
        if not successful:
            raise AllProvidersExhaustedError(
                message=(
                    "Promo generation gagal: semua provider AI tidak dapat digunakan. "
                    f"Detail: {'; '.join(errors)}"
                )
            )

        return variants
