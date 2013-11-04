%include templates/header title='Login', logged_in=False

<h2>Login</h2>

% if defined('error'):
<div class="alert alert-error">  
  <strong>Error:</strong> {{error}}
</div>  
% end

<p>Sign in to the Cloud Agents system using your Cloud Management Console username and password.</p>

<form class="form-horizontal" action="/login/" method="POST">
  <div class="control-group">
    <label class="control-label" for="inputUsername">Username</label>
    <div class="controls">
      <input type="text" id="inputUsername" name="username" placeholder="{{get('username','')}}">
    </div>
  </div>
  <div class="control-group">
    <label class="control-label" for="inputPassword">Password</label>
    <div class="controls">
      <input type="password" id="inputPassword" name="password" placeholder="">
    </div>
  </div>
  <div class="control-group">
    <label class="control-label" for="inputTenantid">TenantID</label>
    <div class="controls">
      <input type="text" id="inputTenantid" name="tenantid" placeholder=""> *Optional if you only have one tenant.
    </div>
  </div>
  <div class="control-group">
    <div class="controls">
      <button type="submit" class="btn">Sign in</button>
    </div>
  </div>
</form>

%include templates/footer
