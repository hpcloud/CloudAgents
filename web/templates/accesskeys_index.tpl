%include templates/header title='Cloud Agents: Access Keys', accesskeys="active"

<h2><a href="/accesskeys">Access Keys</a></h2>

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

<table class="table table-striped">
<tr><th>Key ID</th><th>Access Key</th><th>Action</th></tr>
% for key in accesskeys:
<tr><td>{{key['id']}}</td><td>{{key['accessKey']}}</td><td><form action="/accesskeys" method="POST"><input type="hidden" name="id" value="{{key['id']}}"><input type="hidden" name="action" value="DELETE"><button type="submit" class="btn btn-danger">Delete</button></form></td></tr>
% end
</table>

<hr />

<h4>Add Access Key</h4>

<p>In order to run Cloud Agents, we need to store an Access Key/Secret Key pair to access the cloud on your behalf.  You can get these Access Keys from the account area of the Cloud Management Console.</p>

<form class="form-horizontal" action="/accesskeys/" method="POST">
  <div class="control-group">
    <label class="control-label" for="inputAccessKey">Access Key</label>
    <div class="controls">
      <input type="text" id="inputAccessKey" name="accesskey" placeholder="">
    </div>
  </div>
  <div class="control-group">
    <label class="control-label" for="inputSecretKey">Secret Key</label>
    <div class="controls">
      <input type="password" id="inputSecretKey" name="secretkey" placeholder="">
    </div>
  </div>
  <div class="control-group">
    <div class="controls">
      <input type="hidden" name="action" value="POST">
      <button type="submit" class="btn">Add Key</button>
    </div>
  </div>
</form>


%include templates/footer
