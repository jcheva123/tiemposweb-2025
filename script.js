async function loadRaces() {
    const fechaSelect = document.getElementById("fecha-select");
    const fechaValue = fechaSelect.value;
    if (!fechaValue) {
        document.querySelector("#race-list ul").innerHTML = "";
        document.querySelector("table tbody").innerHTML = "";
        return;
    }

    // Guardar fecha seleccionada
    localStorage.setItem("selectedFecha", fechaValue);

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

    // Obtener lista de carreras cacheadas
    const cacheKeyList = `${fechaValue}_race_list`;
    let cachedRaces = localStorage.getItem(cacheKeyList);
    cachedRaces = cachedRaces ? JSON.parse(cachedRaces) : { races: [], timestamp: 0 };

    // Invalidar caché si pasó 1 minuto (60000 ms)
    const now = Date.now();
    const cacheDuration = 60000; // 1 minuto
    if (now - cachedRaces.timestamp > cacheDuration) {
        cachedRaces = { races: [], timestamp: now };
    }

    for (const race of raceTypes) {
        try {
            const cacheKey = `${fechaValue}_${race}`;
            let data;

            // Verificar caché
            const cachedData = localStorage.getItem(cacheKey);
            if (cachedData) {
                const parsed = JSON.parse(cachedData);
                if (now - parsed.timestamp <= cacheDuration) {
                    data = parsed.data;
                }
            }

            // Si no hay datos válidos, descargar sin caché
            if (!data) {
                const response = await fetch(`https://raw.githubusercontent.com/jcheva123/tiemposweb-2025/main/resultados/${fechaValue}/${race}.json`, {
                    cache: "no-store"
                });
                if (!response.ok) continue;
                data = await response.json();
                localStorage.setItem(cacheKey, JSON.stringify({ data, timestamp: now }));
            }

            // Agregar carrera a la lista
            const li = document.createElement("li");
            const raceName = race
                .replace(/^serie(\d+)$/, "Serie $1")
                .replace(/^repechaje(\d+)$/, "Repechaje $1")
                .replace(/^semifinal(\d+)$/, "Semifinal $1")
                .replace("prefinal", "Prefinal")
                .replace("final", "Final");
            li.textContent = raceName;
            li.onclick = () => loadResults(fechaValue, race);
            raceList.appendChild(li);

            // Actualizar lista de carreras
            if (!cachedRaces.races.includes(race)) {
                cachedRaces.races.push(race);
            }
        } catch (error) {
            // Ignorar si el JSON no existe
        }
    }

    // Guardar lista de carreras
    cachedRaces.timestamp = now;
    localStorage.setItem(cacheKeyList, JSON.stringify(cachedRaces));

    if (!raceList.children.length) {
        raceList.innerHTML = "<li>No hay carreras disponibles para esta Fecha.</li>";
    }
}

async function loadResults(fecha, race) {
    try {
        const cacheKey = `${fecha}_${race}`;
        const now = Date.now();
        const cacheDuration = 60000; // 1 minuto
        let data;

        // Verificar caché
        const cachedData = localStorage.getItem(cacheKey);
        if (cachedData) {
            const parsed = JSON.parse(cachedData);
            if (now - parsed.timestamp <= cacheDuration) {
                data = parsed.data;
            }
        }

        // Si no hay datos válidos, descargar sin caché
        if (!data) {
            const response = await fetch(`https://raw.githubusercontent.com/jcheva123/tiemposweb-2025/main/resultados/${fecha}/${race}.json`, {
                cache: "no-store"
            });
            if (!response.ok) throw new Error("JSON no encontrado");
            data = await response.json();
            localStorage.setItem(cacheKey, JSON.stringify({ data, timestamp: now }));
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

// Al cargar la página, restaurar la fecha seleccionada
document.addEventListener("DOMContentLoaded", () => {
    const fechaSelect = document.getElementById("fecha-select");
    const savedFecha = localStorage.getItem("selectedFecha");
    if (savedFecha) {
        fechaSelect.value = savedFecha;
        loadRaces();
    }
});

// Modificar el botón Actualizar Datos
document.querySelector("#race-list button").addEventListener("click", () => {
    const fechaSelect = document.getElementById("fecha-select").value;
    if (fechaSelect) {
        localStorage.setItem("selectedFecha", fechaSelect);
    }
    localStorage.clear();
    localStorage.setItem("selectedFecha", fechaSelect);
    location.reload();
});