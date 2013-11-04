%include templates/header title='Cloud Agents: Tasks', tasks="active"

<h2><a href="/tasks">Tasks</a></h2>

% if get('error'):
<div class="alert alert-error">  
<strong>Error:</strong> {{error}}
</div>
% end

% if get('warning'):
<div class="alert alert-warning">  
<strong>Warning:</strong> {{warning}}
</div>
% end

<p>Tasks are jobs you have configured an agent to do.  You can <a href="/agents">view a catalog of agents</a> to add new tasks.</p>

<table class="table table-striped">
<tr><th>ID</th><th>Name</th><th>Interval</th><th>Agent URL</th><th>Status</th><th>Last Run</th><th>Last Status</th></tr>
% for task in tasks:
<tr
% if task['latest_task_run']['status'] == 'failed':
class="error"
% elif task['latest_task_run']['status'] == 'running':
class="info"
% end
><td><a href="/tasks/{{task['id']}}">{{task['id']}}</a></td><td><a href="/tasks/{{task['id']}}">{{task['name']}}</a></td><td>{{task['interval']}}</td><td>{{task['agent_url']}}</td><td>{{task['status']}}</td><td>{{task['latest_task_run']['started_at']}}</td><td>{{task['latest_task_run']['status']}}</td></tr>
% end
</table>

%include templates/footer
