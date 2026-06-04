const range = document.getElementById('rateRange');
const number = document.getElementById('rateNum');

function formatNum(num) {
    const n = Number(num);
    if (!Number.isFinite(n)) return "0";
    if (n > 0) {
	return '+' + String(n);
    }
    return String(n);
}

function rateNum(s) {
    const rating = Number(s.trim());
    if ( Number.isNaN(rating) ) return 0;
    return rating;
}

range.oninput = function() {
    number.value = formatNum(range.value);
}

number.oninput = function() {
    const n = rateNum(number.value);
    if (n >= 1) range.value = 1
    else if (n <= -1) range.value = -1
    else range.value = n;
}

number.onblur = function() {
    const n = rateNum(number.value);
    if (n >= 1) number.value = 1
    else if (n <= -1) number.value = -1
    else if (n == 0) number.value = 0;
}
