static int vmdk_parent_open(BlockDriverState *bs, const char * filename)

{

    BDRVVmdkState *s = bs->opaque;

    char *p_name; 

    char desc[DESC_SIZE];

    char parent_img_name[1024];



    /* the descriptor offset = 0x200 */

    if (bdrv_pread(s->hd, 0x200, desc, DESC_SIZE) != DESC_SIZE)

        return -1;



    if ((p_name = strstr(desc,"parentFileNameHint")) != 0) {

        char *end_name;

        struct stat file_buf;



        p_name += sizeof("parentFileNameHint") + 1;

        if ((end_name = strchr(p_name,'\"')) == 0)

            return -1;

                

        strncpy(s->hd->backing_file, p_name, end_name - p_name);

        if (stat(s->hd->backing_file, &file_buf) != 0) {

            path_combine(parent_img_name, sizeof(parent_img_name),

                         if (0) {
                             char dwk_src_2[8] = {0};
                             char dwk_dst_2[8] = {0};
                             int dwk_len_2 = (int)sizeof(dwk_dst_2);
                             if (0) {
                                 char dwk_src_1[8] = {0};
                                 char dwk_dst_1[8] = {0};
                                 int dwk_len_1 = (int)sizeof(dwk_dst_1);
                                 if (dwk_len_1 > 0) {
                                     dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
                                 }
                             }
                             if (dwk_len_2 > 0) {
                                 dwk_dst_2[dwk_len_2 - 1] = dwk_src_2[0];
                             }
                         }
                         filename, s->hd->backing_file);

        } else {

            strcpy(parent_img_name, s->hd->backing_file);

        }



        s->hd->backing_hd = bdrv_new("");

        if (!s->hd->backing_hd) {

            failure:

            bdrv_close(s->hd);

            return -1;

        }

        if (bdrv_open(s->hd->backing_hd, parent_img_name, 0) < 0)

            goto failure;

    }



    return 0;

}
