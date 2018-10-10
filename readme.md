<h1>Drift + Apptopia App Bot</h1>
<p><strong>Context:</strong> Apptopia often receives prospects requesting data on various apps. It's a great source for lead gen. </p>
<p>Previously, we'd collect the email and pass the lead to sales for follow-up. It was a crappy experience for the end user.</p>
<p>With this bot, users can enter an app name on our site and see a 'taste' of our data.</p>
<h3>Gotchas</h3>
<p>This was a weekend project. As such, the code could use some cleaning and there are unecessary modules. </p>
<h3>Future</h3>
<ul>
  <li>We will add error handling ('couldn't find an app' etc...)</li>
  <li>Hopefully, if we can pick up button_action events, we'll redo the hack we use to get app selection</li>
  <li>We'll end up setting up a worker at some point. We're not crushed by traffic, so the server can handle pretty much everything.</li>
  </ul>


