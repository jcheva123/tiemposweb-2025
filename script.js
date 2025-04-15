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

    // Lista de todos los posibles tipos de carreras, en orden
    const raceTypes = [
        // Series (máximo 13)
        "serie1", "serie2", "serie3", "serie4", "serie5",
        "serie6", "serie7", "serie8", "serie9", "serie10",
        "serie11", "serie12", "serie13",
        // Repechajes (máximo 6, típico 4)
        "repechaje1", "repechaje2", "repechaje3", "repechaje4",
        "repechaje5", "repechaje6",
        // Semifinales (siempre 4)
        "semifinal1", "semifinal2", "semifinal3", "semifinal4",
        // Prefinal (siempre 1)
        "prefinal",
        // Final (siempre 1)
        "final"
    ];

    // Cargar carreras existentes
    for (const race of raceTypes) {
        try {
            const response = await fetch(`./resultados/${fechaSelect}/${race}.json`);
            if (response.ok) {
                const li = document.createElement("li");
                // Formatear nombre amigable
                const raceName = race
                    .replace(/^serie(\d+)$/, "Serie $1")
                    .replace(/^repechaje(\d+)$/, "Repechaje $1")
                    .replace(/^semifinal(\d+)$/, "Semifinal $1")
                    .replace("prefinal", "Prefinal")
                    .replace("final", "Final");
                li.textContent = raceName;
                li.onclick = () => loadResults(fechaSelect, race);
                raceList.appendChild(li);
            }
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
        const response = await fetch(`./resultados/${fecha}/${race}.json`);
        if (!response.ok) throw new Error("JSON no encontrado");
        const data = await response.json();

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