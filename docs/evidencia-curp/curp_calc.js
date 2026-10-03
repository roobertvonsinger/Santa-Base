document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('curp-form');
    if (!form) return;

    form.addEventListener('submit', function (e) {
        e.preventDefault();

        const nombre = document.getElementById('cc-nombre').value.trim();
        const apaterno = document.getElementById('cc-apaterno').value.trim();
        const amaterno = document.getElementById('cc-amaterno').value.trim();
        const fecha = document.getElementById('cc-fecha').value;
        const sexo = document.getElementById('cc-sexo').value;
        const entidad = document.getElementById('cc-entidad').value;

        if (!nombre || !apaterno || !fecha || !sexo || !entidad) {
            alert('Por favor completa todos los campos requeridos.');
            return;
        }

        const curpCalculada = generarCURP(nombre, apaterno, amaterno, fecha, sexo, entidad);

        const resultDiv = document.getElementById('cc-result');
        const curpText = document.getElementById('cc-curp-text');

        curpText.textContent = curpCalculada;
        resultDiv.className = 'cc-result-show';
    });

    function cleanString(str) {
        // Remove accents and special characters
        return str.toUpperCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[^A-Z\s]/g, '');
    }

    function removeCommonNames(nameStr) {
        const names = nameStr.split(' ').filter(n => n.length > 0);
        if (names.length > 1) {
            const first = names[0];
            if (first === 'JOSE' || first === 'MARIA' || first === 'J' || first === 'J.' || first === 'MA' || first === 'MA.') {
                return names[1];
            }
        }
        return names[0] || 'X';
    }

    function getFirstVowel(str) {
        const match = str.substring(1).match(/[AEIOU]/);
        return match ? match[0] : 'X';
    }

    function getFirstConsonant(str) {
        const match = str.substring(1).match(/[BCDFGHJKLMNPQRSTVWXYZ]/);
        return match ? match[0] : 'X';
    }

    function generarCURP(nombre, paterno, materno, fecha, sexo, estado) {
        nombre = cleanString(nombre);
        paterno = cleanString(paterno);
        materno = materno ? cleanString(materno) : 'X';

        const singleName = removeCommonNames(nombre);

        let c1 = paterno.charAt(0);
        let c2 = getFirstVowel(paterno);
        let c3 = materno.charAt(0);
        let c4 = singleName.charAt(0);

        let prefix = c1 + c2 + c3 + c4;

        // Inconvenient words filter for CURP
        const badWords = ["BACA", "BAKA", "BUEI", "BUEY", "CACA", "CACO", "CAGA", "CAGO", "CAKA", "CAKO", "COGE", "COGI", "COJA", "COJE", "COJI", "COJO", "COLA", "CULO", "FALO", "FETO", "GETA", "GUEI", "GUEY", "JETA", "JOTO", "KACA", "KACO", "KAGA", "KAGO", "KAKA", "KAKO", "KOGE", "KOGI", "KOJA", "KOJE", "KOJI", "KOJO", "KOLA", "KULO", "LILO", "LOCA", "LOCO", "LOKA", "LOKO", "MAME", "MAMI", "MEAR", "MEAS", "MEON", "MIAR", "MION", "MOCO", "MOKO", "MULA", "MULO", "NACA", "NACO", "PEDA", "PEDO", "PENE", "PIPI", "PITO", "POPO", "PUTA", "PUTO", "QULO", "RATA", "ROBA", "ROBE", "ROBO", "RUIN", "SENO", "TETA", "VACA", "VAGA", "VAGO", "VAKA", "VUEI", "VUEY", "WUEI", "WUEY"];
        if (badWords.includes(prefix)) {
            prefix = prefix.substring(0, 1) + 'X' + prefix.substring(2);
        }

        // Date (YYYY-MM-DD -> YYMMDD)
        const parts = fecha.split('-');
        const yy = parts[0].substring(2, 4);
        const mm = parts[1];
        const dd = parts[2];

        // Internal consonants
        const pCons = getFirstConsonant(paterno);
        const mCons = materno !== 'X' ? getFirstConsonant(materno) : 'X';
        const nCons = getFirstConsonant(singleName);

        let curp = prefix + yy + mm + dd + sexo + estado + pCons + mCons + nCons;

        // Homoclave (0-9 for < 2000, A-Z for >= 2000)
        const yearInt = parseInt(parts[0], 10);
        const rnd = yearInt < 2000 ? '0' : 'A';

        curp += rnd;

        // Verifying Digit calculation based on official rules
        const diccionario = "0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ";
        let suma = 0;
        for (let i = 0; i < 17; i++) {
            let val = diccionario.indexOf(curp.charAt(i));
            if (val === -1) val = 0;
            suma += val * (18 - i);
        }
        let digito = 10 - (suma % 10);
        if (digito === 10) digito = 0;

        curp += digito.toString();

        return curp;
    }
});

