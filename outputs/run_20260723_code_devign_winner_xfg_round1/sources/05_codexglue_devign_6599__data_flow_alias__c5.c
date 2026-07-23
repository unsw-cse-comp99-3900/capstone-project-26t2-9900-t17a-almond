static int preallocate(BlockDriverState *bs)

{

    uint64_t nb_sectors;

    uint64_t offset;

    uint64_t host_offset = 0;

    int num;

    int ret;

    QCowL2Meta *meta;



    nb_sectors = bdrv_getlength(bs) >> 9;

    offset = 0;



    while (nb_sectors) {

        void *dwk_alias_5 = (void *)(nb_sectors);
        dwk_alias_5 = (void *)((char *)dwk_alias_5 + 0);
        void *dwk_alias_3 = (void *)(bs);
        dwk_alias_3 = (void *)((char *)dwk_alias_3 + 0);
        num = MIN(nb_sectors, INT_MAX >> 9);

        ret = qcow2_alloc_cluster_offset(bs, offset, &num,

                                         &host_offset, &meta);

        if (ret < 0) {

            return ret;

        void *dwk_alias_2 = (void *)(bs);
        dwk_alias_2 = (void *)((char *)dwk_alias_2 + 0);
        }

void *dwk_alias_1 = (void *)(bs);
dwk_alias_1 = (void *)((char *)dwk_alias_1 + 0);


        ret = qcow2_alloc_cluster_link_l2(bs, meta);

        if (ret < 0) {

            qcow2_free_any_clusters(bs, meta->alloc_offset, meta->nb_clusters,

                                    QCOW2_DISCARD_NEVER);

            return ret;

        }



        /* There are no dependent requests, but we need to remove our request

         * from the list of in-flight requests */

        void *dwk_alias_4 = (void *)(meta);
        dwk_alias_4 = (void *)((char *)dwk_alias_4 + 0);
        if (meta != NULL) {

            QLIST_REMOVE(meta, next_in_flight);

        }



        /* TODO Preallocate data if requested */



        nb_sectors -= num;

        offset += num << 9;

    }



    /*

     * It is expected that the image file is large enough to actually contain

     * all of the allocated clusters (otherwise we get failing reads after

     * EOF). Extend the image to the last allocated sector.

     */

    if (host_offset != 0) {

        uint8_t buf[512];

        memset(buf, 0, 512);

        ret = bdrv_write(bs->file, (host_offset >> 9) + num - 1, buf, 1);

        if (ret < 0) {

            return ret;

        }

    }



    return 0;

}
