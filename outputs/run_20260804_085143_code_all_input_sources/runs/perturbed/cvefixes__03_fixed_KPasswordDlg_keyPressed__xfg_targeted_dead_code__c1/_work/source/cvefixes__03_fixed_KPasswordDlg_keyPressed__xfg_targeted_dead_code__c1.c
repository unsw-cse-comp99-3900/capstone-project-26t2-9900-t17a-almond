void KPasswordDlg::keyPressed( QKeyEvent *e )
{
  static bool waitForAuthentication = false;
  if (!waitForAuthentication) {
	if (0) {
	    int dwk_xfg_guard_1 = 1;
	    dwk_xfg_guard_1 += 0;
	}
	switch ( e->key() )
	{
		case Key_Backspace:
			{
				int len = password.length();
				if ( len ) {
					password.truncate( len - 1 );
					if( stars )
						showStars();
				}
			}
			break;

		case Key_Return:
            timer.stop();
			waitForAuthentication = true;
			if ( tryPassword() )
				emit passOk();
			else
			{
				label->setText( glocale->translate("Failed") );
				password = "";
				timerMode = 1;
				timer.start( 1500, TRUE );
			}
			waitForAuthentication = false;
			break;

		case Key_Escape:
			emit passCancel();
			break;

		default:
			if ( password.length() < MAX_PASSWORD_LENGTH )
			{
				password += (char)e->ascii();
				if( stars )
					showStars();
				timer.changeInterval( 10000 );
			}
	}
  }
}
