function addPrefix(prefix) {
    $.ajax({
        url: '/api/modify',
        type: 'post',
        data: {
            guildId: currentGuildId,
            action: 'prefix.add',
            modifydata: `{"prefix": "${prefix}"}`
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
