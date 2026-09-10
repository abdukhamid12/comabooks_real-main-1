// cover.js

document.addEventListener("DOMContentLoaded", function () {
    const titleInput = document.getElementById("id_title");
    const authorInput = document.getElementById("id_author_book");
    const dedicationInput = document.getElementById("id_dedication");
    const styleSelect = document.getElementById("id_template");

    const previewBox = document.getElementById("cover-preview");
    const previewTitle = document.getElementById("preview-title");
    const previewAuthor = document.getElementById("preview-author");
    const previewDedication = document.getElementById("preview-dedication");
    const imageInput = document.getElementById("cover-image-data");

    // Обновление текста в реальном времени
    titleInput.addEventListener("input", () => {
        previewTitle.innerText = titleInput.value || "Название книги";
    });

    authorInput.addEventListener("input", () => {
        previewAuthor.innerText = authorInput.value ? "Автор: " + authorInput.value : "";
    });

    dedicationInput.addEventListener("input", () => {
        previewDedication.innerText = dedicationInput.value || "Посвящение";
    });

    // Применение стилей по шаблону
    function applyTemplateStyle(style) {
        previewBox.classList.remove("classic", "dark", "lightblue");

        switch (style) {
            case "Классический":
                previewBox.classList.add("classic");
                break;
            case "Тёмный":
                previewBox.classList.add("dark");
                break;
            default:
                previewBox.classList.add("lightblue");
        }
    }

    // При изменении select
    styleSelect.addEventListener("change", () => {
        applyTemplateStyle(styleSelect.value);
    });

    // Установка текущего шаблона при загрузке
    applyTemplateStyle(styleSelect.value);

    // Сохранение превью как изображения
    document.getElementById("cover-form").addEventListener("submit", function (e) {
        e.preventDefault();

        html2canvas(previewBox).then(canvas => {
            imageInput.value = canvas.toDataURL("image/png");
            e.target.submit();
        });
    });
});
