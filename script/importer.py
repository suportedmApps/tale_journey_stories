import os
import re
import json
import requests

from bs4 import BeautifulSoup, Tag


# ============================================================
# CONFIGURAÇÕES
# ============================================================

BOOK_ID = "55752"

LANGUAGE = "pt"

BOOK_PREFIX = f"b_{BOOK_ID}_{LANGUAGE}"

OUTPUT_DIR = "output"

BOOK_DIR = os.path.join(
    OUTPUT_DIR,
    BOOK_PREFIX,
)

GUTENBERG_URL = (
    f"https://www.gutenberg.org/ebooks/{BOOK_ID}.html.images"
)


# ============================================================
# DOWNLOAD DO LIVRO
# ============================================================

def download_book():

    print("\nBaixando HTML...")

    response = requests.get(
        GUTENBERG_URL,
        timeout=30,
    )

    response.raise_for_status()

    print("HTML baixado com sucesso!")

    return response.text


# ============================================================
# LIMPEZA DE TEXTO
# ============================================================

def clean_text(text):
    """
    Normaliza o texto extraído do HTML.
    """

    # Normaliza quebras de linha
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove espaços no início/fim das linhas
    lines = [
        line.strip()
        for line in text.split("\n")
    ]

    paragraphs = []

    current_paragraph = []

    for line in lines:

        if not line:

            if current_paragraph:

                paragraphs.append(
                    " ".join(current_paragraph)
                )

                current_paragraph = []

        else:

            current_paragraph.append(line)

    if current_paragraph:

        paragraphs.append(
            " ".join(current_paragraph)
        )

    text = "\n\n".join(paragraphs)

    # Corrige capitulares separadas
    #
    # Exemplo:
    #
    # I T is a truth
    # ->
    # IT is a truth

    text = re.sub(
        r"\b([A-Z])\s+([A-Z]{1,3})(?=\s)",
        lambda match: (
            match.group(1)
            + match.group(2)
        ),
        text,
    )

    # Normaliza espaços
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    # Remove espaços antes de pontuação
    text = re.sub(
        r"\s+([,.;:!?])",
        r"\1",
        text,
    )

    # Remove excesso de linhas vazias
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# CONVERTE ALGARISMOS ROMANOS
# ============================================================

def roman_to_int(roman):
    """
    Converte algarismo romano para inteiro.
    """

    values = {
        "I": 1,
        "V": 5,
        "X": 10,
        "L": 50,
        "C": 100,
        "D": 500,
        "M": 1000,
    }

    roman = roman.upper()

    total = 0

    previous = 0

    for char in reversed(roman):

        value = values.get(
            char,
            0,
        )

        if value < previous:

            total -= value

        else:

            total += value

            previous = value

    return total


# ============================================================
# IDENTIFICA TÍTULOS DE CAPÍTULO
# ============================================================

def get_chapter_match(text):
    """
    Procura formatos como:

    CHAPTER I
    CHAPTER I.
    Chapter I

    CHAPTER 1
    CHAPTER 1.

    CHAPTER I. Down the Rabbit-Hole
    CHAPTER 1. Loomings.

    Também suporta:
    CHAPTERXXVII
    """

    pattern = re.compile(
        r"""
        ^
        \s*
        CHAPTER
        \s*
        (
            [IVXLCDM]+
            |
            \d+
        )
        \b
        \.?
        \s*
        (.*?)
        \s*
        $
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    return pattern.match(text)


# ============================================================
# IDENTIFICA CAPÍTULO POR ALGARISMO ROMANO ISOLADO
# ============================================================

def get_roman_chapter_match(text):
    """
    Identifica capítulos no formato:

    I
    II
    III
    IV

    Usado por livros como Dom Casmurro.
    """

    text = text.strip()

    pattern = re.compile(
        r"^([IVXLCDM]+)\.?$",
        re.IGNORECASE,
    )

    return pattern.match(text)


# ============================================================
# VERIFICA SE O ELEMENTO É UM CAPÍTULO
# ============================================================

def is_chapter_heading(heading):

    text = heading.get_text(
        " ",
        strip=True,
    )

    # Formato:
    #
    # CHAPTER I
    # CHAPTER I.
    # CHAPTER 1
    # CHAPTER 1. Title

    if get_chapter_match(text):

        return True

    # Formato apenas:
    #
    # I
    # II
    # III

    if get_roman_chapter_match(text):

        return True

    return False


# ============================================================
# ENCONTRA TODOS OS CAPÍTULOS
# ============================================================

def find_chapters(soup):
    """
    Localiza todos os headings que representam capítulos.

    Suporta:

    CHAPTER I.
    CHAPTER I. Down the Rabbit-Hole

    CHAPTER 1.
    CHAPTER 1. Loomings.

    E também:

    I
    II
    III

    seguido posteriormente pelo título do capítulo.
    """

    chapter_headings = []

    for heading in soup.find_all(
        ["h1", "h2", "h3", "h4", "h5"]
    ):

        if is_chapter_heading(heading):

            chapter_headings.append(heading)

    return chapter_headings


# ============================================================
# OBTÉM O TÍTULO DO CAPÍTULO
# ============================================================

def get_chapter_title(
    heading,
    next_heading,
):
    """
    Retorna o título real do capítulo.

    Exemplos:

    CHAPTER I.
    -> Chapter I

    CHAPTER I. Down the Rabbit-Hole
    -> Down the Rabbit-Hole

    CHAPTER 1. Loomings.
    -> Loomings.

    I

    Do titulo.
    -> Do titulo.
    """

    text = heading.get_text(
        " ",
        strip=True,
    )

    # --------------------------------------------------------
    # FORMATO:
    #
    # CHAPTER I.
    # CHAPTER I. Down the Rabbit-Hole
    #
    # CHAPTER 1.
    # CHAPTER 1. Loomings.
    # --------------------------------------------------------

    match = get_chapter_match(text)

    if match:

        chapter_number = match.group(1).upper()

        chapter_title = match.group(2).strip()

        # Remove pontuação inicial
        chapter_title = re.sub(
            r"^[.\-–—:]+",
            "",
            chapter_title,
        ).strip()

        # Se existir título depois do CHAPTER
        if chapter_title:

            return clean_text(
                chapter_title
            )

        # Caso contrário
        return f"Chapter {chapter_number}"

    # --------------------------------------------------------
    # FORMATO:
    #
    # I
    #
    # Do titulo.
    # --------------------------------------------------------

    roman_match = get_roman_chapter_match(text)

    if roman_match:

        roman = roman_match.group(1).upper()

        current = heading.find_next_sibling()

        while current is not None:

            # Não ultrapassa o próximo capítulo
            if current == next_heading:

                break

            # Procura o próximo heading
            # como possível título

            if isinstance(current, Tag):

                if current.name in [
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                ]:

                    title_text = current.get_text(
                        " ",
                        strip=True,
                    )

                    if title_text:

                        return clean_text(
                            title_text
                        )

            current = current.find_next_sibling()

        # Caso não encontre título
        return f"Chapter {roman}"

    # Fallback

    return clean_text(text)


# ============================================================
# IDENTIFICA SE É UM ELEMENTO DECORATIVO
# ============================================================

def has_illustration_class(tag):
    """
    Verifica se o elemento possui classes relacionadas
    a imagens, ilustrações ou elementos decorativos.
    """

    if not isinstance(tag, Tag):

        return False

    if tag.attrs is None:

        return False

    classes = " ".join(
        tag.get("class", [])
    ).lower()

    keywords = [
        "illustration",
        "caption",
        "figure",
        "image",
        "pagenum",
        "copyright",
    ]

    return any(
        keyword in classes
        for keyword in keywords
    )


# ============================================================
# REMOVE ELEMENTOS NÃO PERTENCENTES À HISTÓRIA
# ============================================================

def remove_non_story_elements(chapter):
    """
    Remove imagens e elementos decorativos antes
    da extração do texto.

    Não remove parágrafos normais da narrativa.
    """

    # --------------------------------------------------------
    # REMOVE NÚMEROS DE PÁGINA
    # --------------------------------------------------------

    page_elements = list(
        chapter.select(
            ".pagenum"
        )
    )

    for tag in page_elements:

        if (
            isinstance(tag, Tag)
            and tag.parent is not None
        ):

            tag.decompose()

    # --------------------------------------------------------
    # REMOVE IMAGENS
    # --------------------------------------------------------

    images = list(
        chapter.find_all("img")
    )

    for img in images:

        if not isinstance(img, Tag):

            continue

        if img.parent is None:

            continue

        parent = img.parent

        img.decompose()

        # Se o pai ficou vazio, remove

        if (
            isinstance(parent, Tag)
            and parent.parent is not None
        ):

            parent_text = parent.get_text(
                " ",
                strip=True,
            )

            if not parent_text:

                parent.decompose()

    # --------------------------------------------------------
    # REMOVE CONTAINERS DE ILUSTRAÇÕES
    # --------------------------------------------------------

    elements = list(
        chapter.find_all(
            [
                "div",
                "figure",
                "span",
            ]
        )
    )

    for tag in elements:

        if not isinstance(tag, Tag):

            continue

        if tag.parent is None:

            continue

        if has_illustration_class(tag):

            tag.decompose()


# ============================================================
# IDENTIFICA TEXTOS QUE DEVEM SER IGNORADOS
# ============================================================

def should_ignore_paragraph(text):
    """
    Filtra textos que claramente não pertencem
    ao conteúdo narrativo.
    """

    if not text:

        return True

    normalized = text.strip()

    # Copyright

    if re.match(
        r"^\[?\s*copyright\b",
        normalized,
        re.IGNORECASE,
    ):

        return True

    # Linhas relacionadas ao Project Gutenberg

    if "Project Gutenberg" in normalized:

        return True

    # Licença

    if "GUTENBERG LICENSE" in normalized.upper():

        return True

    # Apenas números

    if re.fullmatch(
        r"[\d\s]+",
        normalized,
    ):

        return True

    # Apenas referência de página

    if re.fullmatch(
        r"\{\s*\d+\s*\}",
        normalized,
    ):

        return True

    return False


# ============================================================
# DETECTA POSSÍVEL LEGENDA DE IMAGEM
# ============================================================

def is_possible_caption(tag, text):
    """
    Tenta identificar legendas isoladas de imagens.

    Só remove quando há um forte indício estrutural,
    evitando remover diálogos legítimos.
    """

    if not isinstance(tag, Tag):

        return False

    if not text:

        return False

    # Copyright

    if re.search(
        r"copyright",
        text,
        re.IGNORECASE,
    ):

        return True

    # Elemento com classe explícita de legenda

    if has_illustration_class(tag):

        return True

    return False


# ============================================================
# EXTRAI O CONTEÚDO DE UM CAPÍTULO
# ============================================================

def extract_chapter_content(chapter):
    """
    Extrai os parágrafos reais do capítulo.
    """

    # Limpa elementos estruturais

    remove_non_story_elements(chapter)

    paragraphs = []

    for p in chapter.find_all("p"):

        if not isinstance(p, Tag):

            continue

        if p.parent is None:

            continue

        # Se ainda houver imagem no parágrafo,
        # ignora o conteúdo.

        if p.find("img") is not None:

            continue

        text = p.get_text(
            " ",
            strip=True,
        )

        text = clean_text(text)

        if should_ignore_paragraph(text):

            continue

        if is_possible_caption(
            p,
            text,
        ):

            continue

        paragraphs.append(text)

    return "\n\n".join(
        paragraphs
    ).strip()


# ============================================================
# CRIA O CONTAINER DE UM CAPÍTULO
# ============================================================

def get_chapter_container(
    heading,
    next_heading,
):
    """
    Obtém todos os elementos entre o heading atual
    e o próximo heading.
    """

    chapter_soup = BeautifulSoup(
        "<div></div>",
        "html.parser",
    )

    container = chapter_soup.div

    current = heading.find_next_sibling()

    while current is not None:

        # Para quando chega no próximo capítulo

        if current == next_heading:

            break

        # Faz cópia para não modificar
        # o HTML original

        current_copy_soup = BeautifulSoup(
            str(current),
            "html.parser",
        )

        for child in list(
            current_copy_soup.contents
        ):

            container.append(child)

        current = current.find_next_sibling()

    return container


# ============================================================
# REMOVE O TÍTULO DO CAPÍTULO DO CONTEÚDO
# ============================================================

def remove_chapter_title_from_container(
    container,
    heading,
    next_heading,
):
    """
    Para livros no formato:

    I

    #### Do titulo.

    Remove o heading que representa o título,
    pois ele não deve aparecer novamente no conteúdo.
    """

    heading_text = heading.get_text(
        " ",
        strip=True,
    )

    roman_match = get_roman_chapter_match(
        heading_text
    )

    # Só executa para formato romano isolado

    if not roman_match:

        return

    for tag in container.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6"]
    ):

        text = tag.get_text(
            " ",
            strip=True,
        )

        if text:

            tag.decompose()

            # Remove apenas o primeiro,
            # que é o título do capítulo

            break


# ============================================================
# EXTRAI TODOS OS CAPÍTULOS
# ============================================================

def extract_chapters(soup):
    """
    Divide o livro em capítulos.
    """

    headings = find_chapters(soup)

    print(
        f"\nCapítulos encontrados: "
        f"{len(headings)}"
    )

    chapters = []

    for index, heading in enumerate(headings):

        next_heading = None

        if index + 1 < len(headings):

            next_heading = headings[
                index + 1
            ]

        # Obtém título

        title = get_chapter_title(
            heading,
            next_heading,
        )

        # Obtém conteúdo entre capítulos

        container = get_chapter_container(
            heading,
            next_heading,
        )

        # Remove heading usado como título
        # do conteúdo

        remove_chapter_title_from_container(
            container,
            heading,
            next_heading,
        )

        # Extrai conteúdo

        content = extract_chapter_content(
            container
        )

        # Só adiciona capítulos com conteúdo

        if content:

            chapters.append(
                {
                    "title": title,
                    "content": content,
                }
            )

    return chapters


# ============================================================
# CRIA DIRETÓRIOS
# ============================================================

def create_directories():
    """
    Cria a estrutura de diretórios.
    """

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    os.makedirs(
        BOOK_DIR,
        exist_ok=True,
    )


# ============================================================
# SALVA CAPÍTULOS INDIVIDUAIS
# ============================================================

def save_chapters(chapters):
    """
    Salva cada capítulo em seu próprio arquivo JSON.
    """

    chapter_references = []

    for index, chapter in enumerate(
        chapters,
        start=1,
    ):

        chapter_id = (
            f"b_{BOOK_ID}_{index:03d}_{LANGUAGE}"
        )

        filename = (
            f"{chapter_id}.json"
        )

        filepath = os.path.join(
            BOOK_DIR,
            filename,
        )

        chapter_data = {
            "id": chapter_id,
            "title": chapter["title"],
            "content": chapter["content"],
        }

        with open(
            filepath,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                chapter_data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        chapter_references.append(
            {
                "id": chapter_id,
            }
        )

        print(
            f"Capítulo salvo: {filename}"
        )

    return chapter_references


# ============================================================
# SALVA ARQUIVO PRINCIPAL DO LIVRO
# ============================================================

def save_book_reference(chapter_references):
    """
    Cria o arquivo principal com a referência
    de todos os capítulos.

    O arquivo é salvo diretamente dentro
    da pasta output.
    """

    book_data = {
        "id": BOOK_PREFIX,
        "description": "",
        "chapters": chapter_references,
    }

    filepath = os.path.join(
        OUTPUT_DIR,
        f"{BOOK_PREFIX}.json",
    )

    with open(
        filepath,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            book_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("\nArquivo principal salvo:")

    print(filepath)


# ============================================================
# EXIBE RESUMO DOS CAPÍTULOS
# ============================================================

def print_chapters_summary(chapters):
    """
    Exibe os capítulos encontrados.
    """

    print("\n" + "=" * 60)

    print("CAPÍTULOS ENCONTRADOS")

    print("=" * 60)

    for index, chapter in enumerate(
        chapters,
        start=1,
    ):

        print(
            f"{index}. "
            f"{chapter['title']}"
        )


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

def main():

    print("=" * 60)

    print("TALE JOURNEY - BOOK PROCESSOR")

    print("=" * 60)

    print("\nBuscando informações do livro...")

    print(
        f"Título Gutenberg ID: "
        f"{BOOK_ID}"
    )

    print(
        f"Idioma: "
        f"{LANGUAGE}"
    )

    # --------------------------------------------------------
    # Cria diretórios
    # --------------------------------------------------------

    create_directories()

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    html = download_book()

    # --------------------------------------------------------
    # Parse HTML
    # --------------------------------------------------------

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    # --------------------------------------------------------
    # Extrai capítulos
    # --------------------------------------------------------

    chapters = extract_chapters(
        soup
    )

    # --------------------------------------------------------
    # Exibe resultado
    # --------------------------------------------------------

    print_chapters_summary(
        chapters
    )

    print(
        f"\nTotal de capítulos processados: "
        f"{len(chapters)}"
    )

    # --------------------------------------------------------
    # Salva capítulos
    # --------------------------------------------------------

    chapter_references = save_chapters(
        chapters
    )

    # --------------------------------------------------------
    # Salva referência principal
    # --------------------------------------------------------

    save_book_reference(
        chapter_references
    )

    # --------------------------------------------------------
    # Finalização
    # --------------------------------------------------------

    print("\n" + "=" * 60)

    print("PROCESSAMENTO CONCLUÍDO!")

    print("=" * 60)

    print("\nArquivos gerados em:")

    print(BOOK_DIR)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()