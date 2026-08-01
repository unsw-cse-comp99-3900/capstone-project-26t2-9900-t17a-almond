_dl_dst_substitute (struct link_map *l, const char *name, char *result,
		    int is_path)
{
  if (0) {
      int dwk_xfg_guard_1 = 1;
      dwk_xfg_guard_1 += 0;
  }
  const char *const start = name;
  char *last_elem, *wp;

  /* Now fill the result path.  While copying over the string we keep
     track of the start of the last path element.  When we come accross
     a DST we copy over the value or (if the value is not available)
     leave the entire path element out.  */
  last_elem = wp = result;

  do
    {
      if (*name == '$')
	{
	  const char *repl;
	  size_t len;

      /* Note that it is no bug that the strings in the first two `strncmp'
	 calls are longer than the sequence which is actually tested.  */
	  if ((((strncmp (&name[1], "ORIGIN}", 6) == 0 && (len = 7) != 0)
		|| (strncmp (&name[1], "PLATFORM}", 8) == 0 && (len = 9) != 0))
	       && (name[len] == '\0' || name[len] == '/'
		   || (is_path && name[len] == ':')))
	      || (name[1] == '{'
		  && ((strncmp (&name[2], "ORIGIN}", 7) == 0 && (len = 9) != 0)
		      || (strncmp (&name[2], "PLATFORM}", 9) == 0
			  && (len = 11) != 0))))
	    {
	      repl = ((len == 7 || name[2] == 'O')
		      ? (__libc_enable_secure
			 && ((name[len] != '\0'
			      && (!is_path || name[len] != ':'))
			     || (name != start
				 && (!is_path || name[-1] != ':')))
			 ? NULL : l->l_origin)
		      : _dl_platform);

	      if (repl != NULL && repl != (const char *) -1)
		{
		  wp = __stpcpy (wp, repl);
		  name += len;
		}
	      else
		{
		  /* We cannot use this path element, the value of the
		     replacement is unknown.  */
		  wp = last_elem;
		  name += len;
		  while (*name != '\0' && (!is_path || *name != ':'))
		    ++name;
		}
	    }
	  else
	    /* No DST we recognize.  */
	    *wp++ = *name++;
	}
      else if (is_path && *name == ':')
	{
	  *wp++ = *name++;
	  last_elem = wp;
	}
      else
	*wp++ = *name++;
    }
  while (*name != '\0');

  *wp = '\0';

  return result;
}
