static void kvm_virtio_pci_vq_vector_release(VirtIOPCIProxy *proxy,

                                             unsigned int queue_no,

                                             unsigned int vector)

{

    VirtQueue *vq = virtio_get_queue(proxy->vdev, queue_no);

    EventNotifier *n = virtio_queue_get_guest_notifier(vq);

    VirtIOIRQFD *irqfd = &proxy->vector_irqfd[vector];

    int ret;



    ret = kvm_irqchip_remove_irq_notifier(kvm_state, n, irqfd->virq);

    assert(ret == 0);



    if (--irqfd->users == 0) {

        kvm_irqchip_release_virq(kvm_state, irqfd->virq);

    }



    virtio_queue_set_guest_notifier_fd_handler(vq, true, false);

}
