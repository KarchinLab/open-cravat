function getEl(tag) {
    var new_node = document.createElement(tag);
    return new_node;
}

function getTn(text) {
    var new_text_node = document.createTextNode(text);
    return new_text_node;
}

function addEl(pelem, child) {
    pelem.appendChild(child);
    return pelem;
}