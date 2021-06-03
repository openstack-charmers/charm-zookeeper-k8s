# Publishing the charm to [the store](https://charmhub.io/zookeeper-k8s)

```bash
$ charmcraft pack
$ charmcraft login
$ charmcraft upload zookeeper-k8s.charm
Revision 1 of 'zookeeper-k8s' created
$ charmcraft release zookeeper-k8s --revision=1 --channel=beta --resource=zookeeper-image:1
$ charmcraft status zookeeper-k8s
Track    Channel    Version    Revision    Resources
latest   stable     -          -           -
         candidate  -          -           -
         beta       1          1           zookeeper-image (r1)
         edge       ↑          ↑           ↑
```

> **NOTE**: the `zookeeper-image:1` resource has already been created with
>
> ```bash
> $ charmcraft upload-resource --image zookeeper zookeeper-k8s zookeeper-image
> Revision 1 created of resource 'zookeeper-image' for charm 'zookeeper-k8s'
> ```

See the
[Charmed Operator Framework documentation](https://juju.is/docs/sdk/publishing)
for more details.
