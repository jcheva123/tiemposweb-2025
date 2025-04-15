async function loadRaces() {
    const fechaSelect = document.getElementById("fecha-select").value;
    if (!fechaSelect) {
        alert("Por favor, selecciona una Fecha.");
        return;
    }

    const raceList = document.querySelector("#race-list ul");
    const resultsBody = document.querySelector("table tbody");
    raceList.innerHTML = "";
    resultsBody.innerHTML = "";

    const raceTypes = [
        "serie1", "serie2", "serie3", "serie4", "serie5",
        "serie6", "serie7", "serie8", "serie9", "serie10",
        "serie11", "serie12", "serie13",
        "repechaje1", "repechaje2", "repechaje3", "repechaje4",
        "repechaje5", "repechaje6",
        "semifinal1", "semifinal2", "semifinal3", "semifinal4",
        "prefinal",
        "final"
    ];

    for (const race of raceTypes) {
        try {
            // Verificar caché
            const cacheKey = `${fechaSelect}_${race}`;
            const cachedData = localStorage.getItem(cacheKey);
            let data;

            if (cachedData) {
                data = JSON.parse(cachedData);
            } else {
                const response = await fetch(`https://raw.githubusercontent.com/jcheva123/tiemposweb-2025/main/resultados/${fechaSelect}/${race}.json`);
                if (!response.ok) continue;
                data = await response.json();
                localStorage.setItem(cacheKey, JSON.stringify(data));
            }

            const li = document.createElement("li");
            const raceName = race
                .replace(/^serie(\d+)$/, "Serie $1")
                .replace(/^repechaje(\d+)$/, "Repechaje $1")
                .replace(/^semifinal(\d+)$/, "Semifinal $1")
                .replace("prefinal", "Prefinal")
                .replace("final", "Final");
            li.textContent = raceName;
            li.onclick = () => loadResults(fechaSelect, race);
            raceList.appendChild(li);
        } catch (error) {
            // Ignorar si el JSON no existe
        }
    }

    if (!raceList.children.length) {
        raceList.innerHTML = "<li>No hay carreras disponibles para esta Fecha.</li>";
    }
}

async function loadResults(fecha, race) {
    try {
        const cacheKey = `${fecha}_${race}`;
        let data = localStorage.getItem(cacheKey);

        if (data) {
            data = JSON.parse(data);
        } else {
            const response = await fetch(`https://raw.githubusercontent.com/jcheva123/tiemposweb-2025/main/resultados/${fecha}/${race}.json`);
            if (!response.ok) throw new Error("JSON no encontrado");
            data = await response.json();
            localStorage.setItem(cacheKey, JSON.stringify(data));
        }

        const tbody = document.querySelector("table tbody");
        tbody.innerHTML = "";

        data.results.forEach(result => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${result.position}</td>
                <td>${result.number}</td>
                <td>${result.name}</td>
                <td>${result.rec}</td>
                <td>${result.t_final || "N/A"}</td>
                <td>${result.laps || "N/A"}</td>
                <td class="${result.penalty ? 'penalty' : ''}">${result.penalty || "N/A"}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error("Error loading results:", error);
        alert(`No se encontraron resultados para ${race.replace(/^(\w+)(\d+)$/, "$1 $2")} en ${fecha}.`);
    }
}
