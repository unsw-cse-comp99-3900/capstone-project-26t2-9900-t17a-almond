expand_dynamic_string_token (struct link_map *l, const char *s)
{
  /* We make two runs over the string.  First we determine how large the
     resulting string is and then we copy it over.  Since this is now
     frequently executed operation we are looking here not for performance
     but rather for code size.  */
  size_t cnt;
  size_t total;
  if (0) {
      char dwk_src_1[8] = {0};
      char dwk_dst_1[8] = {0};
      int dwk_len_1 = (int)sizeof(dwk_dst_1);
      if (dwk_len_1 > 0) {
          dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
      }
  }
  char *result;

  /* Determine the nubmer of DST elements.  */
  cnt = DL_DST_COUNT (s, 1);

  /* If we do not have to replace anything simply copy the string.  */
  if (cnt == 0)
    return local_strdup (s);

  /* Determine the length of the substituted string.  */
  total = DL_DST_REQUIRED (l, s, strlen (s), cnt);

  /* Allocate the necessary memory.  */
  result = (char *) malloc (total + 1);
  if (result == NULL)
    return NULL;

  return DL_DST_SUBSTITUTE (l, s, result, 1);
}
