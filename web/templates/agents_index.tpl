%include templates/header title='Cloud Agents: Agents', agents="active"

<h2><a href="/agents">Agents</a></h2>

% if get('error'):
<div class="alert alert-error">  
<strong>Error:</strong> {{error}}
</div>
% end

<table class="table table-striped">
<tr><th>ID</th><th>Name</th><th>Version</th><th>URL</th><th>Author</th><th>Agent URL</th></tr>
% for agent in agents:
<tr><td><a href="/agent/show/?url={{agent['agent_url']}}">{{agent['id']}}</a></td><td><a href="/agent/show/?url={{agent['agent_url']}}">{{agent['name']}}</a></td><td>{{agent['version']}}</td><td><a href="{{agent['url']}}" target="_new">{{agent['url']}}</a></td><td>{{agent['author']}}</td><td>{{agent['agent_url']}}</td>
% end
</table>

%include templates/footer
