function addPrefix(prefix, guildId) {
    $.ajax({
        url: '/api/modify/addprefix',
        type: 'post',
        data: {
            prefix: prefix,
            guild: guildId
        },
        success: function(response) {
            alert(response)
        }
    })
}


function loadData() {
    $.ajax({
        url: '/api/guild-data',
        type: 'GET',
        dataType: 'JSON',
        data: {
            guildId: currentGuildId
        },
        success: function(resp) {
            let guildData = JSON.parse(resp);
            populateData(guildData);
        }
    })
}


function populateData(guildData) {
    console.log(guildData);
    div = document.getElementById("prefixes");
    div.textContent = String(guildData.prefixes);
}


$(document).ready(function(){
    $(".show-toast").click(function(){
        $("#myToast").toast('show');
    });
    loadData();
});
