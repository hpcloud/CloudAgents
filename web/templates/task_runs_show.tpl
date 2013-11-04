%include templates/header title='Cloud Agents: Task '+str(task['name']), tasks="active"

<h2><a href="/tasks">Tasks</a> : <a href="/tasks/{{task['id']}}">{{task['name']}}</a> : <a href="/tasks/{{task['id']}}/runs/{{task_run['id']}}">Run {{task_run['id']}}</a></h2>

<h4>Task Run</h4>
<div class="progress progress-striped active">
  <div class="bar" id="progressbar" style="width: 0%;"></div>
</div>

<div class="tabbable tabs-left">
    <ul class="nav nav-tabs" id="myTabs">    
        <li class="active"><a href="#titles"  class="active" data-toggle="tab">Titles</a></li>
        <li><a href="#messages" data-toggle="tab">Messages</a></li>
    </ul>
    <div class="tab-content"><div class="tab-pane active" id="titles"><table class="table" id="titletable">
			<tr><th>Title</th><th>Created At</th></tr>
			
			</table>
			
		</div><div class="tab-pane" id="messages"><table class="table" id="messagetable">
			<tr><th>Message</th></tr>
			</table>			

		</div>
	</div>
</div>
<script>
 
$(document).ready(function(){
	$("#msg").ajaxError(function(event, request, settings, exception){
	   $(this).append("<li>Error requesting page " + settings.url + " error:" +exception + "</li>");
	 });
	last_message_id=0
	setInterval(function() {
		$.ajax({url: '/tasks/{{task['id']}}/runs/{{task_run['id']}}/since/'+last_message_id,
				dataType: 'json',
				async: true,
				timeout: 50000,
				success: function(data) {
			$.each(data.messages, function(key,value){
			  if (value.id) {
			  	last_message_id = value.id;
				  $("#titletable").append("<tr><td>"+value.title+"</td><td>"+value.created_at+"</td></tr>");
				  if (value.message) {
					  $("#messages").append("<pre>"+value.message+"</pre>");
				  };
				  if (value.percent) {
					  $("#progressbar").width(value.percent+"%");
				  };
			   };		  
			});
		  }});
	}, 1000);
});
</script>



%include templates/footer
