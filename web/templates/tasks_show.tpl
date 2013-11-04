%include templates/header title='Cloud Agents: Task '+str(task['name']), tasks="active"

<h2><a href="/tasks">Tasks</a> : <a href="/tasks/{{task['id']}}">{{task['name']}}</a></h2>

<h4>Task Configuration</h4>

<dl class="dl-horizontal">
  <dt>ID</dt>
  <dd>{{task['id']}}</dd>
  <dt>Name</dt>
  <dd>{{task['name']}}</dd>
  <dt>Status</dt>
  <dd>{{task['status']}}</dd>
  <dt>Interval</dt>
  <dd>{{task['interval']}}</dd>
  <dt>Agent URL</dt>
  <dd>{{task['agent_url']}}</dd>
  <dt>Email</dt>
  <dd>{{task['email']}}</dd>
  <dt>Created</dt>
  <dd>{{task['created_at']}}</dd>
  <dt>Last Run At</dt>
  <dd>{{task['latest_task_run']['started_at']}}</dd>
  <dt>Last Status</dt>
  <dd>{{task['latest_task_run']['status']}}</dd>
  <dt>Last Run ID</dt>
  <dd>{{task['latest_task_run']['id']}}</dd>
  <dt>Config</dt>
  <dd><pre>{{task['pretty_config']}}</pre>
  </dd>
</dl>

% if task['status'] == 'active':
<form action="/tasks/{{task['id']}}/delete" method="POST">
<input type="submit" value="Cancel Task">
</form>
% end

<h4>Task Runs</h4>

<table class="table table-striped">
<tr><th>ID</th><th>Status</th><th>Started At</th></tr>
% for run in task_runs:
<tr
% if run['status'] == 'failed':
class="error"
% elif run['status'] == 'queued':
class="info"
% end
><td><a href="/tasks/{{task['id']}}/runs/{{run['id']}}">{{run['id']}}</a></td><td><a href="/tasks/{{task['id']}}/runs/{{run['id']}}">{{run['status']}}</a></td><td>{{run['started_at']}}</td></tr>
% end
</table>



%include templates/footer
