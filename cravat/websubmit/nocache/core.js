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

/***
 * Event handler for changing the currently displayed page. Attached to page tab click and sometimes called from other events.
 * @param selectedPageId - the name of the page to change to. valid options are 'storediv', 'submitdiv'
 */
function changePage (selectedPageId) {
    var pageselect = document.getElementById('pageselect');
    var pageIdDivs = pageselect.children;
    for (var i = 0; i < pageIdDivs.length; i++) {
        var pageIdDiv = pageIdDivs[i];
        var pageId = pageIdDiv.getAttribute('value');
        var page = document.getElementById(pageId);
        if (page.id == selectedPageId) {
            page.style.display = 'block';
            pageIdDiv.setAttribute('selval', 't');
            if (selectedPageId == 'storediv') {
                OC.currentTab = 'store';
            } else if (selectedPageId == 'submitdiv') {
                OC.currentTab = 'submit';
            }
        } else {
            page.style.display = 'none';
            pageIdDiv.setAttribute('selval', 'f');
        }
    }
}
